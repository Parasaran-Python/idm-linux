import unittest
import io
import sys
from unittest.mock import MagicMock, patch
from idm_cli.cli import build_parser, run_cli_command


class TestCLI(unittest.TestCase):
    def test_parser_add(self):
        parser = build_parser()
        args = parser.parse_args(["add", "https://example.com/file.zip", "--connections", "16", "--later"])
        self.assertEqual(args.command, "add")
        self.assertEqual(args.url, "https://example.com/file.zip")
        self.assertEqual(args.connections, 16)
        self.assertTrue(args.later)

    def test_parser_list(self):
        parser = build_parser()
        args = parser.parse_args(["list", "--status", "downloading", "--category", "Compressed"])
        self.assertEqual(args.command, "list")
        self.assertEqual(args.status, "downloading")
        self.assertEqual(args.category, "Compressed")

    def test_run_cli_command_mock(self):
        mock_client = MagicMock()
        mock_client.send_request.return_value = {"status": "ok", "download_id": "dl-mock123"}

        parser = build_parser()
        args = parser.parse_args(["add", "https://example.com/test.zip"])
        
        ret = run_cli_command(args, client=mock_client)
        self.assertEqual(ret, 0)
        mock_client.send_request.assert_called_once()


if __name__ == "__main__":
    unittest.main()
