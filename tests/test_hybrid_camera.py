"""Hybrid capture: same-tick grab/retrieve and single blink count."""

from __future__ import annotations

import unittest

from app.hybrid_camera import (
    FusedBlinkRate,
    any_on_screen_face,
    camera_try_order,
    grab_all,
    hybrid_decode_indices,
    hybrid_should_count_blink,
    is_front_facing,
    missing_camera_indices,
    next_hybrid_fill_wait,
    pick_best_index,
    pick_front_facing_index,
    read_frames_synced,
    retrieve_frame,
    should_drop_silent_hybrid_camera,
    view_quality,
)


class _FakeCap:
    def __init__(self, frame, *, grab_ok: bool = True, retrieve_ok: bool = True):
        self.frame = frame
        self.grab_ok = grab_ok
        self.retrieve_ok = retrieve_ok
        self.grabs = 0
        self.retrieves = 0
        self.order: list[str] = []

    def grab(self) -> bool:
        self.grabs += 1
        self.order.append("grab")
        return bool(self.grab_ok)

    def retrieve(self):
        self.retrieves += 1
        self.order.append("retrieve")
        if not self.retrieve_ok:
            return False, None
        return True, self.frame


class HybridCaptureTests(unittest.TestCase):
    def test_grab_all_cameras_before_any_retrieve(self) -> None:
        """Every camera is sampled first; pixels are decoded second."""
        log: list[str] = []

        class OrderedCap(_FakeCap):
            def __init__(self, name: str, frame: str):
                super().__init__(frame)
                self.name = name

            def grab(self) -> bool:
                log.append(f"{self.name}:grab")
                return super().grab()

            def retrieve(self):
                log.append(f"{self.name}:retrieve")
                return super().retrieve()

        a = OrderedCap("a", "fa")
        b = OrderedCap("b", "fb")
        out = read_frames_synced({0: a, 1: b}, drain=0)
        self.assertEqual(out, {0: "fa", 1: "fb"})
        self.assertEqual(log, ["a:grab", "b:grab", "a:retrieve", "b:retrieve"])

    def test_drain_grabs_before_the_synced_sample(self) -> None:
        a = _FakeCap("fa")
        b = _FakeCap("fb")
        read_frames_synced({0: a, 1: b}, drain=2)
        self.assertEqual(a.grabs, 3)
        self.assertEqual(b.grabs, 3)
        self.assertEqual(a.retrieves, 1)
        self.assertEqual(b.retrieves, 1)

    def test_failed_grab_omits_that_camera(self) -> None:
        a = _FakeCap("fa", grab_ok=False)
        b = _FakeCap("fb")
        out = read_frames_synced({0: a, 1: b})
        self.assertEqual(out, {1: "fb"})
        self.assertEqual(a.retrieves, 0)
        self.assertEqual(b.retrieves, 1)

    def test_grab_all_does_not_decode(self) -> None:
        a = _FakeCap("fa")
        b = _FakeCap("fb")
        ready = grab_all({0: a, 1: b})
        self.assertEqual(set(ready), {0, 1})
        self.assertEqual(a.retrieves, 0)
        self.assertEqual(b.retrieves, 0)
        self.assertEqual(retrieve_frame(a), "fa")
        self.assertEqual(a.retrieves, 1)
        self.assertEqual(b.retrieves, 0)

    def test_camera_try_order_puts_sticky_first(self) -> None:
        self.assertEqual(camera_try_order(1, [0, 1, 2]), [1, 0, 2])
        self.assertEqual(camera_try_order(None, [2, 0]), [2, 0])
        self.assertEqual(camera_try_order(9, [0, 1]), [0, 1])

    def test_hybrid_decode_only_sticky_until_hunt(self) -> None:
        self.assertEqual(hybrid_decode_indices([0, 1], 1, hunt=False), [1])
        self.assertEqual(hybrid_decode_indices([0, 1], 1, hunt=True), [1, 0])
        self.assertEqual(hybrid_decode_indices([0, 1], None, hunt=False), [0])
        self.assertEqual(hybrid_decode_indices([], 0, hunt=True), [])

    def test_pick_front_facing_ignores_profile_when_another_is_frontal(self) -> None:
        views = [
            (0, True, False, False, 40.0),  # face, on-screen, turned
            (1, True, False, True, 8.0),   # face, on-screen, front-facing
            (2, False, False, True, 0.0),  # no face
        ]
        self.assertEqual(pick_front_facing_index(views), 1)
        self.assertFalse(
            is_front_facing(face_found=True, off_screen=False, is_frontal=False)
        )
        self.assertTrue(
            is_front_facing(face_found=True, off_screen=False, is_frontal=True)
        )

    def test_pick_front_facing_falls_back_when_none_are_frontal(self) -> None:
        views = [
            (0, True, False, False, 35.0),
            (1, True, False, False, 18.0),
        ]
        self.assertEqual(pick_front_facing_index(views), 1)

    def test_pick_best_prefers_on_screen_frontal_face(self) -> None:
        views = [
            (0, True, True, True, 5.0),    # face, off-screen
            (1, True, False, True, 12.0),  # face, on-screen, frontal
            (2, False, False, True, 0.0),  # no face
        ]
        self.assertEqual(pick_best_index(views), 1)
        self.assertGreater(
            view_quality(
                face_found=True, off_screen=False, is_frontal=True, face_angle_deg=8.0
            ),
            view_quality(
                face_found=True, off_screen=True, is_frontal=True, face_angle_deg=2.0
            ),
        )

    def test_pick_front_facing_keeps_sticky_when_still_frontal(self) -> None:
        views = [
            (0, True, False, True, 12.0),
            (1, True, False, True, 8.0),
        ]
        self.assertEqual(pick_front_facing_index(views, sticky=0), 0)
        self.assertEqual(pick_front_facing_index(views, sticky=1), 1)
        self.assertEqual(pick_front_facing_index(views), 1)

    def test_pick_front_facing_leaves_sticky_when_it_is_no_longer_frontal(self) -> None:
        views = [
            (0, True, False, False, 40.0),
            (1, True, False, True, 10.0),
        ]
        self.assertEqual(pick_front_facing_index(views, sticky=0), 1)

    def test_any_on_screen_face_ignores_look_away_views(self) -> None:
        self.assertTrue(any_on_screen_face([(True, False), (True, True)]))
        self.assertFalse(any_on_screen_face([(True, True), (False, False)]))
        self.assertFalse(any_on_screen_face([]))

    def test_hybrid_counts_blink_finished_on_extra_camera(self) -> None:
        self.assertTrue(
            hybrid_should_count_blink(
                counting=True,
                chosen_counted=False,
                chosen_off_screen=False,
                extra_counts=[(True, False)],
            )
        )
        self.assertFalse(
            hybrid_should_count_blink(
                counting=True,
                chosen_counted=False,
                chosen_off_screen=False,
                extra_counts=[(True, True)],
            )
        )
        self.assertFalse(
            hybrid_should_count_blink(
                counting=False,
                chosen_counted=True,
                chosen_off_screen=False,
                extra_counts=[(True, False)],
            )
        )

    def test_fused_rate_counts_once_inside_refractory(self) -> None:
        rate = FusedBlinkRate()
        self.assertTrue(rate.allow(0.0, refractory_s=0.25))
        rate.on_blink(10, 0.0)
        self.assertEqual(rate.count, 1)
        self.assertFalse(rate.allow(0.10, refractory_s=0.25))
        self.assertTrue(rate.allow(0.30, refractory_s=0.25))
        rate.on_blink(310, 0.30)
        self.assertEqual(rate.count, 2)
        self.assertEqual(rate.bpm(310), 2.0)

    def test_fused_rate_hold_shifts_window(self) -> None:
        rate = FusedBlinkRate()
        rate.on_blink(1_000, 1.0)
        rate.hold_rate_across_gap(5_000)
        self.assertEqual(rate.bpm(6_000), 1.0)
        self.assertEqual(rate.bpm(66_001), 0.0)

    def test_missing_camera_indices(self) -> None:
        self.assertEqual(missing_camera_indices([0, 1], [1]), [0])
        self.assertEqual(missing_camera_indices([0, 1], [0, 1]), [])
        self.assertEqual(missing_camera_indices([2, 0], [2]), [0])

    def test_drop_silent_camera_only_when_another_is_live(self) -> None:
        self.assertTrue(
            should_drop_silent_hybrid_camera(24, others_live=True, threshold=24)
        )
        self.assertFalse(
            should_drop_silent_hybrid_camera(23, others_live=True, threshold=24)
        )
        self.assertFalse(
            should_drop_silent_hybrid_camera(100, others_live=False, threshold=24)
        )

    def test_hybrid_fill_wait_backs_off(self) -> None:
        self.assertEqual(next_hybrid_fill_wait(0), 5.0)
        self.assertEqual(next_hybrid_fill_wait(1), 10.0)
        self.assertEqual(next_hybrid_fill_wait(2), 20.0)
        self.assertEqual(next_hybrid_fill_wait(3), 30.0)
        self.assertEqual(next_hybrid_fill_wait(8), 30.0)


if __name__ == "__main__":
    unittest.main()
