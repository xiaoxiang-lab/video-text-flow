"""阶段 2 链校验：05-拆镜作业单 → design.json → handoff.md → manifest 文件存在性。

用法：python checks/check_stage2.py <05-拆镜作业单.md> <项目目录>
输出：JSON 报告，非零退出码 = 有违规。

校验项（全部确定性，程序层 0 漂移）：
a. 05→design narration 逐字链：design.shots[i].narration == 05 表格第 i 行旁白
   （VOX 硬约束：narration 逐字切分定稿；23a/23b 在 05 与 design 均为独立行，行序一致）
b. 05→design 时长：design.duration_seconds = 配音实测（正数即可，不再要求整秒档位——
   2026-08-17 修复：synthesize-narration 写回实测后旧校验假报 41 条）；
   05 表格档位 vs flow_slot(实测) 的偏差只进 stats.stale_slots（05 是配音前估算）
c. 05→design 参考图集合：05 标 ✅ 的镜序 == design 带 image_prompt 的镜序（缺/多都违规）
d. 05→design image_prompt 逐字：05 参考图节引用块 == design.image_prompt
e. design 内部：每镜 narration/video_prompt 非空；相邻镜背景不同（每镜换背景）；
   尾部按差值分档（余量镜「结尾稳定/保持完全静止/定格」；补差镜「末帧」+稳定——srt-vox 第 6 节翻译）；
   差值硬规律：实测 ≥3s ⟹ |flow_slot(实测) − 实测| ≤ 1.0；短镜（<3s）≤ 3.2
f. handoff vs design：镜数/旁白/时长/参考图标记逐镜一致（防生成 bug 与手动改坏）；
   handoff「Flow 档位」行 == flow_slot(实测)（2026-08-17：旧正则匹配「建议时长」对真实产物
   静默失效，修复并新增档位一致性）
g. manifest 状态 vs 产物文件：master/参考图/handoff 按 stages 存在
h. 差值率（解释型 |差值| 合计 ÷ 生成总时长）>20% → warnings（提示项，不 fail）

规则假设来源：CLAUDE.md（VOX 硬约束 narration 边界）+ guide.zh.md（每镜换背景）
+ srt-vox storyboard-algorithm 第 5/6 节（吸附表/差值/尾部契约，2026-08-17 翻译）
+ 阶段 1 关卡 5 对抗性回查 P3（口头确认 ≠ 程序化，必须落到校验器）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_jobcard

VALID_DURATIONS = (4, 6, 8, 10)


def flow_slot(seconds: float) -> int:
    """就近吸附（分界 5/7/9，srt-vox 第 5 节翻译）；<3s 为短镜取 4 秒地板。"""
    if seconds < 3.0:
        return 4
    return min(VALID_DURATIONS, key=lambda c: (abs(c - seconds), c))

# 05 参考图节标题：**H 镜（…）** 或 **17 镜（…）**
IMG_SECTION_RE = re.compile(r"\*\*(H|\d+[a-z]?)\s*镜")
# video_prompt 背景行
BG_RE = re.compile(r"背景是([^。\n]+)。")
# handoff 镜块
HANDOFF_SHOT_RE = re.compile(r"^## (shot-\d+) (.*)$", re.M)
# 真实产物格式：Flow 档位：6s（旁白真实时长 5.8s）（2026-08-17 起主格式）
HANDOFF_FLOW_RE = re.compile(r"Flow 档位：(\d+)s（旁白真实时长 ([\d.]+)s）")
# 旧测试格式兜底：建议时长：X.Xs
HANDOFF_DUR_RE = re.compile(r"建议时长：([\d.]+)s")
HANDOFF_REF_RE = re.compile(r"参考图：上传 `(\.\./03-images\\references\\[\w-]+\.png)`")
HANDOFF_NOREF_RE = re.compile(r"本镜不上传参考图")

# 尾部契约（srt-vox 第 6 节翻译，2026-08-17）：按差值分类检查尾部语义
# 余量/正好：尾部须有稳定落点（防模型在没规定的静止段自行发挥）
TAIL_SURPLUS_RE = re.compile(r"结尾稳定|保持完全静止|定格")
# 补差：末帧必须物理稳定（会被定格延长）；「结尾稳定保持 0.8 秒」等 0.8s 静止已满足，
# 剪辑提示语（这一帧会被定格延长）属文档规则，不进程序检查（防误报旧句式）
TAIL_STABLE_RE = re.compile(r"稳定|静止|定格|不动")


def _norm(text: str) -> str:
    """空白归一化（保留标点与数字——narration 逐字链不允许标点漂移）。"""
    return re.sub(r"\s+", "", text)


def _clean(text: str) -> str:
    """子序列比较用：去标点、统一大小写（srt-vox 7b 同款）。"""
    return "".join(ch for ch in _norm(text).lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def extract_img_prompts(job05: str) -> dict[str, str]:
    """提取 05 参考图节：镜号 → 引用块文本（去 > 前缀）。"""
    out = {}
    cur = None
    buf = []
    for line in job05.splitlines():
        m = IMG_SECTION_RE.search(line)
        if m:
            if cur:
                out[cur] = _norm("\n".join(buf))
            cur = m.group(1)
            buf = []
        elif cur and line.strip().startswith(">"):
            buf.append(line.strip().lstrip(">").strip())
    if cur:
        out[cur] = _norm("\n".join(buf))
    return out


def check_job05_vs_design(job05: str, design: dict) -> tuple[list[str], list[str]]:
    """05→design 链。返回 (issues, stale_slots)。

    stale_slots = 05 表格档位 vs flow_slot(配音实测) 的偏差记录（05 是配音前估算，
    配音后以实测为准，不算违规；handoff 建议档位才是最终）。
    """
    issues = []
    stale_slots = []
    table = check_jobcard.parse_table(job05)
    shots = design.get("shots") or []
    if not table:
        return ["05 未解析到作业表行（| 镜号 | 时长档 | 旁白 | 参考图 | 动作要点 |）"], stale_slots
    if not shots:
        return ["design.json 无 shots（空或缺失）"], stale_slots
    if len(table) != len(shots):
        issues.append(f"镜数不符：05 表格 {len(table)} 镜 vs design {len(shots)} 镜")

    img_prompts = extract_img_prompts(job05)
    for i, row in enumerate(table):
        sid = i + 1
        if i >= len(shots):
            break
        shot = shots[i]
        # a. narration 逐字
        if _norm(shot.get("narration") or "") != _norm(row["narration"]):
            issues.append(
                f"第 {i + 1} 镜（05 镜号 {row['no']}）narration 不一致："
                f"05[{row['narration']}] vs design[{shot.get('narration')}]")
        # b. 时长：design.duration_seconds = 配音实测，正数即可（2026-08-17 修复假报）
        dur = shot.get("duration_seconds")
        if not isinstance(dur, (int, float)) or dur <= 0:
            issues.append(f"第 {i + 1} 镜（{row['no']}）时长非法：{dur}（必须为正数，配音实测秒数）")
        else:
            want = flow_slot(float(dur))
            if want != row["dur"]:
                stale_slots.append(
                    f"第 {i + 1} 镜（{row['no']}）05 档位 {row['dur']}s vs 配音实测 {dur}s 就近吸附 {want}s"
                    f"（05 是估算，handoff 以实测为准）")
        # c. 参考图
        has_img = "image_prompt" in shot
        if row["ref"] and not has_img:
            issues.append(f"第 {i + 1} 镜（{row['no']}）参考图缺失：05 标 ✅ 但 design 无 image_prompt")
        if not row["ref"] and has_img:
            issues.append(f"第 {i + 1} 镜（{row['no']}）参考图多余：05 未标 ✅ 但 design 有 image_prompt")
        # d. image_prompt 逐字
        if has_img and row["no"] in img_prompts:
            got = _norm(shot["image_prompt"])
            want = img_prompts[row["no"]]
            if got != want:
                issues.append(
                    f"第 {i + 1} 镜（{row['no']}）image_prompt 不一致：05 节 vs design 文本"
                    f"（05[{want[:40]}] vs design[{got[:40]}]）")
        elif has_img and row["no"] not in img_prompts:
            issues.append(f"第 {i + 1} 镜（{row['no']}）有 image_prompt 但 05 参考图节无该镜")
    return issues, stale_slots


def check_design_internal(design: dict) -> list[str]:
    """design 内部一致性 + 差值/尾部契约（srt-vox 第 5/6 节翻译）。

    尾部按差值分类：
      - 余量/正好（flow_slot(实测) ≥ 实测）：尾部含「结尾稳定/保持完全静止/定格」
      - 补差（flow_slot(实测) < 实测，仅短镜/超档出现）：尾部含「末帧」+ 稳定语义
        （末帧会被剪辑定格延长，裁尾无效）
    差值硬规律：实测 ≥3s ⟹ |flow_slot(实测) − 实测| ≤ 1.0；短镜（<3s）上限 3.2。
    """
    issues = []
    shots = design.get("shots")
    if not isinstance(shots, list) or not shots:
        return ["design.json 必须包含非空 shots 列表"]
    prev_bg = None
    for i, shot in enumerate(shots, 1):
        if not isinstance(shot, dict):
            issues.append(f"第 {i} 镜不是对象")
            continue
        for field in ("narration", "video_prompt"):
            if not isinstance(shot.get(field), str) or not shot[field].strip():
                issues.append(f"第 {i} 镜缺少非空 {field}")
        vp = shot.get("video_prompt") or ""
        dur = shot.get("duration_seconds")
        shot_type = shot.get("type")
        # 差值规则（有实测时长才查；flow_slot 保证吸附，防未来实现回归）
        if isinstance(dur, (int, float)) and dur > 0:
            slot = flow_slot(float(dur))
            delta = slot - float(dur)
            # 例外二（第 3 轮）：展示型自然 >11s 封顶 10s，补差可超 1.0（平台上限）
            is_display_cap = shot_type == "展示" and float(dur) > 11.0
            if float(dur) < 3.0:
                if abs(delta) > 3.2 + 0.051:
                    issues.append(f"第 {i} 镜短镜差值 {delta:+.2f}s 超上限 3.2s（4s 地板 − 0.8s 下限）")
            elif abs(delta) > 1.0 + 0.051 and not is_display_cap:
                issues.append(
                    f"第 {i} 镜差值 {delta:+.2f}s 破硬规律（实测 {dur}s ≥ 3s ⟹ |差值| ≤ 1.0s）")
            # 尾部契约分档
            if delta < 0:
                # 补差镜：末帧必须物理稳定（剪辑里定格延长，裁尾无效）
                if not TAIL_STABLE_RE.search(vp):
                    issues.append(
                        f"第 {i} 镜补差 {delta:+.2f}s（{dur}s 就近取 {slot}s）：video_prompt 尾部"
                        f"必须含「稳定/静止/定格」——末帧会被定格延长，裁尾无效")
            elif not TAIL_SURPLUS_RE.search(vp):
                issues.append(f"第 {i} 镜尾部缺稳定落点（余量 {delta:+.2f}s）："
                              f"需含「结尾稳定/保持完全静止/定格」——模型会在没规定的静止段自行发挥")
        elif "结尾稳定保持 0.8 秒" not in vp:
            issues.append(f"第 {i} 镜缺时长无法按差值分档，尾部至少需含「结尾稳定保持 0.8 秒」")
        m = BG_RE.search(vp)
        if m:
            bg = m.group(1).strip()
            if bg == prev_bg:
                issues.append(f"第 {i - 1}/{i} 镜背景连续同底（{bg}）——每镜换背景")
            prev_bg = bg
        # 展示型逐字覆盖（第 3 轮，srt-vox 7b 翻译）：旁白必须是上屏文字（image_prompt）的子序列
        if shot_type == "展示" and "image_prompt" in shot:
            narration = _clean(shot.get("narration") or "")
            onscreen = _clean(shot.get("image_prompt") or "")
            if narration and not _is_subsequence(narration, onscreen):
                issues.append(f"第 {i} 镜展示型上屏文字未完整覆盖旁白："
                              f"旁白须逐字出现在 image_prompt（拆卡不砍字，超长按语义断点拆）")
    return issues


def _is_subsequence(needle: str, haystack: str) -> bool:
    it = iter(haystack)
    return all(ch in it for ch in needle)


def compute_delta_rate(shots: list[dict]) -> tuple[float | None, list[str]]:
    """差值率（srt-vox 第 6 节翻译）：解释型 |差值| 合计 ÷ 生成总时长。

    展示型（type=展示）排除——封顶/定格路线与解释型不同。>20% 提示（不 fail）。
    """
    warnings = []
    total_delta = 0.0
    total_gen = 0.0
    for shot in shots:
        if shot.get("type") == "展示":
            continue
        dur = shot.get("duration_seconds")
        if not isinstance(dur, (int, float)) or dur <= 0:
            continue
        slot = flow_slot(float(dur))
        total_delta += abs(slot - float(dur))
        total_gen += slot
    if total_gen <= 0:
        return None, warnings
    rate = total_delta / total_gen
    if rate > 0.20:
        warnings.append(
            f"差值率 {rate:.1%} > 20%——成因多为 4s 档镜偏多/短镜；"
            f"选项：a. 接受（逐镜写收束动作）b. 并列短镜合成一镜 c. 回配音稿合并过碎句")
    return rate, warnings


def parse_handoff(text: str) -> list[dict]:
    """解析 handoff.md 为逐镜 dict：id/title/dur/narration/has_ref/slot。

    dur 优先取「Flow 档位」行的旁白真实时长（2026-08-17 起主格式），
    兜底旧「建议时长」格式。slot = handoff 标注的 Flow 档位。
    """
    shots = []
    for m in HANDOFF_SHOT_RE.finditer(text):
        sid = m.group(1)
        block = text[m.end():]
        nxt = HANDOFF_SHOT_RE.search(block)
        if nxt:
            block = block[: nxt.start()]
        flow_m = HANDOFF_FLOW_RE.search(block)
        dur_m = HANDOFF_DUR_RE.search(block)
        nar_m = re.search(r"^> (.+)$", block, re.M)
        has_ref = bool(HANDOFF_REF_RE.search(block))
        no_ref = bool(HANDOFF_NOREF_RE.search(block))
        shots.append({
            "id": sid,
            "title": m.group(2).strip(),
            "dur": float(flow_m.group(2)) if flow_m else (float(dur_m.group(1)) if dur_m else None),
            "slot": int(flow_m.group(1)) if flow_m else None,
            "narration": nar_m.group(1).strip() if nar_m else "",
            "has_ref": has_ref,
            "no_ref": no_ref,
        })
    return shots


def check_handoff_vs_design(design: dict, handoff_text: str) -> list[str]:
    issues = []
    shots = design.get("shots") or []
    handoff_shots = parse_handoff(handoff_text)
    if not handoff_shots:
        return ["handoff.md 未解析到任何镜块（## shot-XXX）"]
    if len(shots) != len(handoff_shots):
        issues.append(f"镜数不符：design {len(shots)} 镜 vs handoff {len(handoff_shots)} 镜")
    for i, (shot, hs) in enumerate(zip(shots, handoff_shots), 1):
        expect_id = f"shot-{i:03d}"
        if hs["id"] != expect_id:
            issues.append(f"第 {i} 镜 handoff id 不符：{hs['id']}（期望 {expect_id}）")
        if _norm(hs["narration"]) != _norm(shot.get("narration") or ""):
            issues.append(f"第 {i} 镜 handoff 旁白与 design 不一致（{expect_id}）")
        dur = shot.get("duration_seconds")
        if hs["dur"] is None:
            issues.append(f"第 {i} 镜（{expect_id}）handoff 缺时长行"
                          f"（需「Flow 档位：Xs（旁白真实时长 X.Xs）」）")
        elif isinstance(dur, (int, float)) and dur > 0 and abs(hs["dur"] - dur) > 0.051:
            issues.append(f"第 {i} 镜 handoff 旁白时长 {hs['dur']}s vs design {dur}s")
        # Flow 档位 == flow_slot(实测)（就近吸附，2026-08-17）
        if hs["slot"] is not None and isinstance(dur, (int, float)) and dur > 0:
            want = flow_slot(float(dur))
            if hs["slot"] != want:
                issues.append(f"第 {i} 镜（{expect_id}）handoff Flow 档位 {hs['slot']}s "
                              f"≠ 就近吸附 {want}s（实测 {dur}s，分界 5/7/9）")
        has_ref = "image_prompt" in shot
        if has_ref and not hs["has_ref"]:
            issues.append(f"第 {i} 镜（{expect_id}）handoff 缺参考图标记（design 有 image_prompt）")
        if not has_ref and hs["has_ref"]:
            issues.append(f"第 {i} 镜（{expect_id}）handoff 多了参考图标记（design 无 image_prompt）")
        if not has_ref and not hs["no_ref"]:
            issues.append(f"第 {i} 镜（{expect_id}）handoff 缺「本镜不上传参考图」标注")
    return issues


def check_manifest_files(manifest_path: Path, project_dir: Path) -> list[str]:
    issues = []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stages = manifest.get("stages") or {}
    images = project_dir / "03-images"
    if stages.get("images") == "completed":
        if (manifest.get("master") or {}).get("status") in ("downloaded", "approved"):
            if not (images / "master.png").exists():
                issues.append("manifest 标记 images=completed 但 03-images/master.png 不存在")
        for sid, entry in (manifest.get("shots") or {}).items():
            if entry.get("status") in ("downloaded", "approved"):
                if not (images / "references" / f"{sid}.png").exists():
                    issues.append(f"manifest 标记 {sid} 已生成但 03-images/references/{sid}.png 不存在")
    if stages.get("image-review") == "completed":
        for sid, entry in (manifest.get("shots") or {}).items():
            if entry.get("status") != "approved":
                issues.append(f"image-review=completed 但 {sid} 状态为 {entry.get('status')}（应 approved）")
    if stages.get("handoff-export") == "completed":
        handoff = project_dir / "04-prompts" / "handoff.md"
        if not handoff.exists():
            issues.append("manifest 标记 handoff-export=completed 但 04-prompts/handoff.md 不存在")
    return issues


def run(job05_path: Path, project_dir: Path) -> dict:
    job05_path = Path(job05_path)
    project_dir = Path(project_dir)
    if not job05_path.exists():
        raise FileNotFoundError(f"05 拆镜作业单不存在：{job05_path}")
    job05 = job05_path.read_text(encoding="utf-8")
    work = project_dir / ".work"
    design_path = work / "design.json"
    manifest_path = work / "manifest.json"
    handoff_path = project_dir / "04-prompts" / "handoff.md"

    missing = [str(p.relative_to(project_dir)) for p in (design_path, manifest_path) if not p.exists()]
    if missing:
        raise FileNotFoundError("阶段 2 产物缺失：" + ", ".join(missing))

    design = json.loads(design_path.read_text(encoding="utf-8"))
    issues = []
    warnings = []
    job_issues, stale_slots = check_job05_vs_design(job05, design)
    issues += job_issues
    issues += check_design_internal(design)
    if handoff_path.exists():
        issues += check_handoff_vs_design(design, handoff_path.read_text(encoding="utf-8"))
    else:
        issues.append("handoff.md 不存在（未 export-handoff 或已删除）")
    issues += check_manifest_files(manifest_path, project_dir)
    delta_rate, rate_warnings = compute_delta_rate(design.get("shots") or [])
    warnings += rate_warnings + stale_slots

    return {"pass": not issues, "issues": issues,
            "job05": str(job05_path), "project": str(project_dir),
            "warnings": warnings,
            "stats": {"design_shots": len(design.get("shots") or []),
                      "refs": sum(1 for s in design.get("shots") or [] if "image_prompt" in s),
                      "delta_rate": round(delta_rate, 4) if delta_rate is not None else None,
                      "stale_slots": len(stale_slots)}}


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("用法：python checks/check_stage2.py <05-拆镜作业单.md> <项目目录>", file=sys.stderr)
        return 2
    try:
        report = run(Path(argv[1]), Path(argv[2]))
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
