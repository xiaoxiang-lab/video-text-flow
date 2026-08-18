"""编排全部阶段。唯一改 manifest 的地方。"""

from __future__ import annotations

import json
from pathlib import Path

from . import handoff as handoff_mod
from . import media
from . import narration as narration_mod
from . import planning
from . import qa
from . import sheet
from .adapter import AdapterError, get_image_adapter
from .state import ProjectWorkspace, atomic_write, file_hash, stable_hash
from .style import StyleError, get_style


class PipelineError(Exception):
    pass


class Pipeline:
    def __init__(self, ws: ProjectWorkspace, config: dict, root: Path):
        self.ws = ws
        self.config = config
        self.root = Path(root)

    # ---------- 基础 ----------

    def _style(self, manifest: dict) -> dict:
        profiles = self.root / self.config["style"]["profiles_dir"]
        try:
            return get_style(profiles, manifest["style"])
        except StyleError:
            raise

    def _default_seconds(self, style: dict) -> float:
        return float(style.get("default_shot_seconds") or self.config["workflow"]["default_shot_seconds"])

    def _require_design(self, project_id: str) -> dict:
        manifest = self.ws.load_manifest(project_id)
        design = planning.require_design(self.ws.design_path(project_id))
        fp = planning.design_fingerprint(design)
        if manifest.get("design_fingerprint") != fp:
            was_exported = (manifest["stages"].get("handoff-export") == "completed"
                            or manifest.get("handoff_stale"))
            for stage in ("design-review", "images", "image-review", "handoff-export"):
                manifest["stages"][stage] = "pending"
            if was_exported:
                manifest["handoff_stale"] = True
            manifest["design_fingerprint"] = fp
            manifest["stages"]["design"] = "completed"
            self.ws.write_manifest(project_id, manifest)
        elif manifest["stages"].get("design") != "completed":
            manifest["stages"]["design"] = "completed"
            self.ws.write_manifest(project_id, manifest)
        return design

    def _plan(self, project_id: str, design: dict) -> list[dict]:
        style = self._style(self.ws.load_manifest(project_id))
        return planning.make_plan(design, default_seconds=self._default_seconds(style))

    def _require_design_review(self, project_id: str) -> None:
        """出图门禁：design.json 必须经独立子 agent 复核并标记通过，否则拒绝。"""
        manifest = self.ws.load_manifest(project_id)
        if manifest["stages"].get("design-review") != "completed":
            raise PipelineError(
                "design.json 未复核（design-review 未完成）。先跑独立子 agent 逐镜复核，"
                "异常处理完后再运行 `python -m voxvideo review-design --project <id>` 标记通过。")

    def review_design(self, project_id: str) -> dict:
        """子 agent 复核通过后标记 design-review=completed。"""
        self._require_design(project_id)
        manifest = self.ws.load_manifest(project_id)
        manifest["stages"]["design-review"] = "completed"
        self.ws.write_manifest(project_id, manifest)
        return {"project": project_id, "design_review": "completed"}

    def _image_shots(self, plan: list[dict]) -> list[dict]:
        return [s for s in plan if "image" in s]

    def _master_prompt(self, project_id: str, manifest: dict) -> str:
        project_file = self.ws.master_prompt_path(project_id)
        if project_file.exists():
            return project_file.read_text(encoding="utf-8")
        style = self._style(manifest)
        rel = style["master_prompt_file"]
        return (self.root / rel).read_text(encoding="utf-8")

    def _image_fingerprint(self, prompt: str, master_hash: str | None) -> str:
        agnes = self.config.get("agnes") or {}
        payload = {"prompt": prompt, "model": agnes.get("model", "agnes-image-2.1-flash"),
                   "size": agnes.get("size", "2K"), "ratio": agnes.get("ratio", "16:9")}
        if master_hash:
            payload["master_file_hash"] = master_hash
        return stable_hash(payload)

    def _adapter(self, adapter=None):
        if adapter is not None:
            return adapter
        env = narration_mod.load_env_file(self.root / ".env")
        return get_image_adapter(self.config, env=env)

    def _ensure_available(self, adapter) -> None:
        """真正提交之前检查一次。不可用时报带出路的错。"""
        if not adapter.available():
            name = getattr(adapter, "name", "unknown")
            raise AdapterError(
                f"图片后端 {name!r} 不可用。两条出路："
                f"① 配好它的凭证（export {name.upper()}_API_KEY=... 或填进 .env）；"
                "② 切换后端（export IMAGE_ADAPTER=kling），"
                "或者把 image_prompt 从 design.json 全部去掉。"
            )

    # ---------- 配音 ----------

    def synthesize_narration(self, project_id: str, narrator=None, patch_probe=None,
                             patch_concat=None) -> dict:
        media.require_audio_tools()
        env = narration_mod.load_env_file(self.root / ".env")
        if narrator is None:
            narrator = narration_mod.narrator_from_config(self.config, env)
        design = self._require_design(project_id)
        plan = self._plan(project_id, design)
        manifest = self.ws.load_manifest(project_id)

        texts = [(s["id"], s["narration"]) for s in plan]
        fingerprint = stable_hash({
            "texts": [t for _, t in texts],
            **{k: v for k, v in narrator.describe().items() if k != "provider"},
        })
        existing = manifest.get("narration") or {}
        narration_file = self.ws.narration_path(project_id)
        if (existing.get("status") == "completed"
                and existing.get("input_fingerprint") == fingerprint
                and narration_file.exists() and narration_file.stat().st_size > 0):
            return {"status": "skipped", "narration_wav": str(narration_file)}

        probe_fn = patch_probe or media.probe
        concat_fn = patch_concat or media.concat_audio

        durations = {}
        takes = []
        for shot_id, text in texts:
            take = self.ws.take_path(project_id, shot_id)
            narrator.synthesize(text, take)
            info = probe_fn(take)
            duration = info.get("duration")
            if not duration:
                style = self._style(manifest)
                duration = self._default_seconds(style)
            durations[shot_id] = round(float(duration), 2)
            takes.append(take)

        concat_fn(takes, narration_file)
        for shot in plan:
            if shot["id"] in durations:
                design["shots"][shot["index"] - 1]["duration_seconds"] = durations[shot["id"]]
        atomic_write(self.ws.design_path(project_id),
                     json.dumps(design, ensure_ascii=False, indent=2) + "\n")

        manifest["narration"] = {
            "status": "completed",
            "input_fingerprint": fingerprint,
            "file_sha256": file_hash(narration_file),
            "durations": {k: durations[k] for k, _ in texts},
            **{k: v for k, v in narrator.describe().items() if k != "provider"},
        }
        manifest["stages"]["narration"] = "completed"
        manifest["design_fingerprint"] = None  # 重算镜长后强制重新 plan
        self.ws.write_manifest(project_id, manifest)
        if hasattr(narrator, "close"):
            narrator.close()
        return {"status": "completed", "narration_wav": str(narration_file),
                "durations": durations}

    # ---------- 图片 ----------

    def _wait_image(self, adapter, entry: dict, dest) -> None:
        try:
            adapter.wait_and_download(entry["submit_id"], dest)
        except TimeoutError:
            raise  # 保留 submit_id，重跑继续轮询
        except Exception:
            entry.pop("submit_id", None)
            raise

    def generate_images(self, project_id: str, adapter=None, shot_ids=None) -> dict:
        self._require_design_review(project_id)
        design = self._require_design(project_id)
        plan = self._plan(project_id, design)
        manifest = self.ws.load_manifest(project_id)
        image_shots = self._image_shots(plan)

        if not image_shots:
            manifest["stages"]["images"] = "completed"
            manifest["stages"]["image-review"] = "completed"
            self.ws.write_manifest(project_id, manifest)
            return {"images_needed": 0, "master": None, "shots": [], "failures": []}

        if shot_ids:
            known = {s["id"] for s in image_shots}
            for sid in shot_ids:
                if sid not in known:
                    raise PipelineError(f"{sid} 这镜没有 image_prompt（不生成参考图）。想补参考图是改 design.json 的事。")

        adapter = self._adapter(adapter)
        self._ensure_available(adapter)
        failures = {}
        shot_entries = manifest.setdefault("shots", {})

        # 母板
        master_prompt = self._master_prompt(project_id, manifest)
        master_entry = manifest["master"]
        master_dest = self.ws.master_path(project_id)
        master_fp = self._image_fingerprint(master_prompt, None)
        if (master_entry.get("status") in ("downloaded", "approved")
                and master_dest.exists() and master_dest.stat().st_size > 0
                and master_entry.get("input_fingerprint") == master_fp):
            master_state = "skipped"
        else:
            try:
                if (master_entry.get("submit_id")
                        and master_entry.get("input_fingerprint") == master_fp
                        and master_entry.get("status") != "failed"):
                    self._wait_image(adapter, master_entry, master_dest)
                else:
                    submit = adapter.generate(master_prompt, master_dest)
                    master_entry.update({"submit_id": submit["submit_id"], "status": "submitted",
                                         "input_fingerprint": master_fp})
                    self.ws.write_manifest(project_id, manifest)
                    self._wait_image(adapter, master_entry, master_dest)
                master_entry["status"] = "downloaded"
                master_entry["file_sha256"] = file_hash(master_dest)
                master_entry.pop("submit_id", None)
                master_state = "downloaded"
            except TimeoutError as exc:
                failures["master"] = f"提交成功但轮询超时（可重跑继续等）：{exc}"
            except Exception as exc:
                failures["master"] = str(exc)
                master_entry["status"] = "failed"
                master_entry.pop("submit_id", None)
        self.ws.write_manifest(project_id, manifest)

        master_hash = None
        if master_dest.exists() and master_dest.stat().st_size > 0:
            master_hash = file_hash(master_dest)

        # 参考图
        results = []
        targets = [s for s in image_shots if not shot_ids or s["id"] in shot_ids]
        for shot in targets:
            sid = shot["id"]
            prompt = shot["image"]["prompt"]
            entry = shot_entries.setdefault(sid, {"status": "pending"})
            dest = self.ws.reference_path(project_id, sid)
            fp = self._image_fingerprint(prompt, master_hash)
            if (entry.get("status") in ("downloaded", "approved")
                    and dest.exists() and dest.stat().st_size > 0
                    and entry.get("input_fingerprint") == fp):
                results.append({"shot_id": sid, "status": "skipped"})
                continue
            try:
                if (entry.get("submit_id")
                        and entry.get("input_fingerprint") == fp
                        and entry.get("status") != "failed"):
                    self._wait_image(adapter, entry, dest)
                else:
                    submit = adapter.generate_with_reference(prompt, master_dest, dest)
                    entry.update({"submit_id": submit["submit_id"], "status": "submitted",
                                  "input_fingerprint": fp, "prompt": prompt})
                    self.ws.write_manifest(project_id, manifest)
                    self._wait_image(adapter, entry, dest)
                entry["status"] = "downloaded"
                entry["file_sha256"] = file_hash(dest)
                entry.pop("submit_id", None)
                entry.pop("failed_reason", None)
                results.append({"shot_id": sid, "status": "downloaded"})
            except TimeoutError as exc:
                entry["status"] = "submitted"
                entry["failed_reason"] = str(exc)
                failures[sid] = f"提交成功但轮询超时（可重跑继续等）：{exc}"
            except Exception as exc:
                entry["status"] = "failed"
                entry["failed_reason"] = str(exc)
                entry.pop("submit_id", None)
                failures[sid] = str(exc)
            self.ws.write_manifest(project_id, manifest)

        manifest["image_failures"] = failures
        all_done = all(
            (manifest["shots"].get(s["id"]) or {}).get("status") in ("downloaded", "approved")
            for s in image_shots
        )
        if failures or not all_done:
            manifest["stages"]["images"] = "pending"
        else:
            manifest["stages"]["images"] = "completed"
            manifest["stages"]["image-review"] = "needs-review"
        self.ws.write_manifest(project_id, manifest)

        if failures:
            detail = "\n".join(f"- {k}: {v}" for k, v in failures.items())
            raise AdapterError(f"部分图片失败（其余已继续跑完）：\n{detail}")
        return {"images_needed": len(image_shots), "master": master_state,
                "shots": results, "failures": []}

    def approve_images(self, project_id: str) -> dict:
        design = self._require_design(project_id)
        plan = self._plan(project_id, design)
        manifest = self.ws.load_manifest(project_id)
        image_shots = self._image_shots(plan)

        if not image_shots:
            manifest["stages"]["images"] = "completed"
            manifest["stages"]["image-review"] = "completed"
            self.ws.write_manifest(project_id, manifest)
            return {"approved": [], "note": "无参考图，无需审核"}

        pending = []
        approved = []
        candidates = []
        master_entry = manifest["master"]
        if master_entry.get("status") in ("downloaded", "approved"):
            candidates.append(("母板", self.ws.master_path(project_id), master_entry))
        else:
            pending.append("母板未生成或未下载，先运行 generate-images")
        for shot in image_shots:
            sid = shot["id"]
            entry = manifest["shots"].get(sid) or {}
            if entry.get("status") in ("downloaded", "approved"):
                candidates.append((sid, self.ws.reference_path(project_id, sid), entry))
            elif entry.get("status") == "failed":
                pending.append(f"{sid} 生成失败，先 retry-image")
            else:
                pending.append(f"{sid} 尚未生成，先运行 generate-images")

        if pending:
            raise PipelineError("以下图片还不能审核：\n- " + "\n- ".join(pending))

        bad = []
        for label, path, entry in candidates:
            try:
                qa.validate_image_file(path)
            except qa.QaError as exc:
                bad.append(f"{label}: {exc}")
        if bad:
            raise qa.QaError("审核拒绝，文件损坏：\n- " + "\n- ".join(bad))

        for label, _, entry in candidates:
            if entry.get("status") != "approved":
                entry["status"] = "approved"
                approved.append(label)
        manifest["stages"]["images"] = "completed"
        manifest["stages"]["image-review"] = "completed"
        self.ws.write_manifest(project_id, manifest)
        return {"approved": approved, "note": None}

    def retry_image(self, project_id: str, shot_id: str, prompt_file, adapter=None) -> dict:
        design = self._require_design(project_id)
        plan = self._plan(project_id, design)
        manifest = self.ws.load_manifest(project_id)
        image_shots = self._image_shots(plan)
        if shot_id not in {s["id"] for s in image_shots}:
            raise PipelineError(
                f"{shot_id} 这镜没有 image_prompt，不能重抽。想给它补一张是改 design.json 的事。"
            )
        prompt = Path(prompt_file).read_text(encoding="utf-8").strip()
        if not prompt:
            raise PipelineError(f"提示词文件为空：{prompt_file}")

        master_dest = self.ws.master_path(project_id)
        if not master_dest.exists() or master_dest.stat().st_size == 0:
            raise PipelineError("母板不存在，先运行 generate-images 生成母板。")
        master_hash = file_hash(master_dest)

        adapter = self._adapter(adapter)
        self._ensure_available(adapter)
        entry = manifest["shots"].setdefault(shot_id, {"status": "pending"})
        dest = self.ws.reference_path(project_id, shot_id)
        fp = self._image_fingerprint(prompt, master_hash)
        submit = adapter.generate_with_reference(prompt, master_dest, dest)
        entry.update({"submit_id": submit["submit_id"], "status": "submitted",
                      "input_fingerprint": fp, "prompt": prompt})
        self.ws.write_manifest(project_id, manifest)
        try:
            adapter.wait_and_download(submit["submit_id"], dest)
        except TimeoutError:
            raise  # 保留 submit_id
        except Exception:
            entry.pop("submit_id", None)
            entry["status"] = "failed"
            self.ws.write_manifest(project_id, manifest)
            raise
        entry["status"] = "downloaded"
        entry["file_sha256"] = file_hash(dest)
        entry.pop("submit_id", None)
        entry.pop("failed_reason", None)
        manifest["image_failures"].pop(shot_id, None)
        manifest["stages"]["image-review"] = "pending"
        if manifest["stages"].get("handoff-export") == "completed" or manifest.get("handoff_stale"):
            manifest["handoff_stale"] = True
        manifest["stages"]["handoff-export"] = "pending"
        self.ws.write_manifest(project_id, manifest)
        return {"shot_id": shot_id, "status": "downloaded", "reapproved_required": True}

    # ---------- 导出 ----------

    def export_handoff(self, project_id: str) -> dict:
        design = self._require_design(project_id)
        plan = self._plan(project_id, design)
        manifest = self.ws.load_manifest(project_id)
        image_shots = self._image_shots(plan)
        master = manifest["master"] if image_shots else None

        handoff_mod.check_export_ready(manifest, image_shots, master)
        narration_ready = (self.ws.narration_path(project_id).exists()
                           and (manifest.get("narration") or {}).get("status") == "completed")
        sheet.write_preview(design, plan, self.ws.preview_path(project_id))
        handoff_mod.write_handoff(design, plan, manifest, project_id, narration_ready,
                                  self.ws.handoff_path(project_id))
        manifest["stages"]["handoff-export"] = "completed"
        manifest["handoff_stale"] = False
        self.ws.write_manifest(project_id, manifest)
        return {"handoff": str(self.ws.handoff_path(project_id))}

    # ---------- 状态 ----------

    def status(self, project_id: str) -> dict:
        try:
            design = self._require_design(project_id)
            design_valid = True
        except Exception as exc:
            design = None
            design_valid = f"{exc}"
        manifest = self.ws.load_manifest(project_id)
        plan = self._plan(project_id, design) if design else None
        image_shots = self._image_shots(plan or [])
        total = len(image_shots)
        approved = sum(
            1 for s in image_shots
            if (manifest["shots"].get(s["id"]) or {}).get("status") == "approved"
        )
        return {
            "project_id": project_id,
            "stages": manifest["stages"],
            "design_valid": design_valid,
            "image_counts": {"total_with_images": total, "approved": approved},
            "master": manifest["master"].get("status"),
            "shots": {
                sid: entry.get("status") for sid, entry in sorted(manifest["shots"].items())
            },
            "image_failures": manifest["image_failures"],
            "handoff_stale": manifest.get("handoff_stale", False),
            "narration": {k: v for k, v in (manifest.get("narration") or {}).items()
                          if k != "input_fingerprint"},
            "files": {
                "handoff": self.ws.handoff_path(project_id).exists(),
                "preview": self.ws.preview_path(project_id).exists(),
                "narration_wav": self.ws.narration_path(project_id).exists(),
                "master_png": self.ws.master_path(project_id).exists(),
            },
        }

    def resume(self, project_id: str) -> dict:
        design = self._require_design(project_id)
        plan = self._plan(project_id, design)
        manifest = self.ws.load_manifest(project_id)
        actions = []
        stopped = False

        if manifest["stages"].get("narration") != "completed":
            if self.ws.narration_path(project_id).exists():
                manifest["stages"]["narration"] = "completed"
            else:
                actions.append("配音未做：运行 synthesize-narration（需要 FISH_API_KEY/FISH_VOICE_ID + ffmpeg），或跳过它继续。")

        image_shots = self._image_shots(plan)
        if not image_shots:
            manifest["stages"]["images"] = "completed"
            manifest["stages"]["image-review"] = "completed"
        else:
            entries = [manifest["shots"].get(s["id"]) or {} for s in image_shots]
            statuses = [e.get("status") for e in entries]
            if statuses and all(s in ("downloaded", "approved") for s in statuses):
                manifest["stages"]["images"] = "completed"
                if not all(s == "approved" for s in statuses):
                    manifest["stages"]["image-review"] = "needs-review"
                    actions.append("图片已生成但未审核：请查看 03-images/ 每一张，满意后运行 approve-images。")
                    stopped = True
                else:
                    manifest["stages"]["image-review"] = "completed"
            else:
                actions.append("图片未生成完：运行 generate-images。")
                stopped = True
        self.ws.write_manifest(project_id, manifest)

        if not stopped and manifest["stages"].get("handoff-export") != "completed":
            self.export_handoff(project_id)
            actions.append("handoff.md 已导出。")
        if not stopped and manifest["stages"].get("handoff-export") == "completed":
            actions.append("全部就绪：交付物已导出，接下来由人手工出片。")
        return {"actions": actions, "stopped": stopped}
