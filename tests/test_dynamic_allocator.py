import unittest
from idm_core.dynamic_allocator import DynamicAllocator, Segment


class TestDynamicAllocator(unittest.TestCase):
    def test_initial_partition_even(self):
        allocator = DynamicAllocator(total_bytes=1000, num_connections=4)
        segs = allocator.get_segments()
        self.assertEqual(len(segs), 4)
        self.assertEqual(segs[0].start_byte, 0)
        self.assertEqual(segs[0].end_byte, 249)
        self.assertEqual(segs[1].start_byte, 250)
        self.assertEqual(segs[1].end_byte, 499)
        self.assertEqual(segs[2].start_byte, 500)
        self.assertEqual(segs[2].end_byte, 749)
        self.assertEqual(segs[3].start_byte, 750)
        self.assertEqual(segs[3].end_byte, 999)

    def test_initial_partition_stream_or_single_byte(self):
        allocator = DynamicAllocator(total_bytes=0, num_connections=8)
        segs = allocator.get_segments()
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0].start_byte, 0)
        self.assertEqual(segs[0].end_byte, -1)

        allocator_one = DynamicAllocator(total_bytes=1, num_connections=8)
        segs_one = allocator_one.get_segments()
        self.assertEqual(len(segs_one), 1)
        self.assertEqual(segs_one[0].start_byte, 0)
        self.assertEqual(segs_one[0].end_byte, 0)

    def test_dynamic_resegmentation_split(self):
        total = 10 * 1024 * 1024
        allocator = DynamicAllocator(total_bytes=total, num_connections=2, min_split_size=1024 * 1024)
        
        allocator.update_progress(0, 5 * 1024 * 1024)
        allocator.mark_completed(0)

        allocator.update_progress(1, 1 * 1024 * 1024)

        split_result = allocator.request_subchunk_split(min_split_size=1024 * 1024)
        self.assertIsNotNone(split_result)
        source_idx, new_seg = split_result
        self.assertEqual(source_idx, 1)
        self.assertEqual(new_seg.index, 2)

        seg1 = allocator.get_segment(1)
        self.assertEqual(new_seg.start_byte, seg1.end_byte + 1)
        self.assertEqual(new_seg.end_byte, total - 1)
        self.assertEqual(new_seg.current_byte, new_seg.start_byte)

    def test_progress_tracking_and_completion(self):
        allocator = DynamicAllocator(total_bytes=400, num_connections=2)
        allocator.update_progress(0, 200)
        allocator.mark_completed(0)
        self.assertFalse(allocator.is_complete())
        self.assertEqual(allocator.get_total_downloaded(), 200)

        allocator.update_progress(1, 200)
        allocator.mark_completed(1)
        self.assertTrue(allocator.is_complete())
        self.assertEqual(allocator.get_total_downloaded(), 400)


if __name__ == "__main__":
    unittest.main()
