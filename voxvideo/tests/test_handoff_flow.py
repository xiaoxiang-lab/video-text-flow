"""handoff 的 Flow 档位吸附测试：真实旁白时长 → 就近吸附档位（4/6/8/10，分界 5/7/9）。

2026-08-17 第 2 轮：向上取整 → 就近吸附（srt-vox 第 5 节翻译）。
硬规律：自然时长 ≥ 3 秒时 |差值（档位 − 实测）| ≤ 1.0 秒。
"""

import unittest

from voxvideo.handoff import flow_slot


class FlowSlotTest(unittest.TestCase):
    def test_exact_slots(self):
        self.assertEqual(flow_slot(4.0), 4)
        self.assertEqual(flow_slot(6.0), 6)
        self.assertEqual(flow_slot(8.0), 8)
        self.assertEqual(flow_slot(10.0), 10)

    def test_nearest_slot(self):
        self.assertEqual(flow_slot(3.4), 4)
        self.assertEqual(flow_slot(5.76), 6)
        self.assertEqual(flow_slot(7.52), 8)
        self.assertEqual(flow_slot(9.5), 10)

    def test_delta_within_1s_for_ge_3s(self):
        # 硬规律：自然 ≥ 3s ⟹ |档位 − 实测| ≤ 1.0（>11s 属拆分/封顶档，不适用）
        for seconds in (3.0, 3.4, 4.99, 5.01, 6.0, 6.99, 7.5, 8.99, 9.01, 10.0, 10.99, 11.0):
            slot = flow_slot(seconds)
            self.assertLessEqual(abs(slot - seconds), 1.001, f"{seconds}s -> {slot}s")

    def test_boundaries_5_7_9(self):
        # 分界点落在 5/7/9：5.0 → 4（等距取小档），7.0 → 6，9.0 → 8
        self.assertEqual(flow_slot(5.0), 4)
        self.assertEqual(flow_slot(5.1), 6)
        self.assertEqual(flow_slot(7.0), 6)
        self.assertEqual(flow_slot(7.1), 8)
        self.assertEqual(flow_slot(9.0), 8)
        self.assertEqual(flow_slot(9.1), 10)

    def test_over_10s_caps_at_10(self):
        self.assertEqual(flow_slot(11.68), 10)

    def test_short_shot_below_3s_floor_4(self):
        # 短镜：< 3s 无 2 秒档，4 秒是地板
        self.assertEqual(flow_slot(2.56), 4)
        self.assertEqual(flow_slot(2.9), 4)

    def test_edge_just_over_slot(self):
        # 就近吸附：4.01 → 4（不是 6），6.01 → 6（不是 8）
        self.assertEqual(flow_slot(4.01), 4)
        self.assertEqual(flow_slot(6.01), 6)


if __name__ == "__main__":
    unittest.main()
