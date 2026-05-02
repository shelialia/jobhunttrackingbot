import os
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")

from jobtracker.bot.commands import scan as scan_cmd


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)


def _user():
    return {
        "gmail_token_json": "{}",
        "last_scanned_at": None,
        "last_manual_scanned_at": None,
        "timezone": "Asia/Singapore",
    }


def _cycle():
    return {
        "id": 42,
        "name": "Test Cycle",
        "started_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }


class ScanPatch:
    def __init__(
        self,
        classification_result,
        *,
        insert_task=None,
        link_application=None,
        count_interviews=None,
        update_interview=None,
        find_existing_interview=None,
    ):
        self.classification_result = classification_result
        self.insert_task = insert_task or Mock(return_value=99)
        self.link_application = link_application or Mock(return_value=10)
        self.count_interviews = count_interviews or Mock(return_value=0)
        self.update_interview = update_interview or Mock()
        self.find_existing_interview = find_existing_interview or Mock(return_value=None)
        self.stack = ExitStack()

    def __enter__(self):
        self.stack.enter_context(patch.object(scan_cmd.cycles_db, "get_active_cycle", Mock(return_value=_cycle())))
        self.stack.enter_context(patch.object(scan_cmd, "fetch_new_messages", Mock(return_value=[{"id": "gmail-1"}])))
        self.stack.enter_context(patch.object(scan_cmd, "get_gmail_id", Mock(return_value="gmail-1")))
        self.stack.enter_context(patch.object(scan_cmd, "get_email_date", Mock(return_value="2026-01-02 10:00:00")))
        self.stack.enter_context(
            patch.object(
                scan_cmd,
                "extract_subject_and_body",
                Mock(return_value=("Interview details", "Here are possible questions for your interview.")),
            )
        )
        self.stack.enter_context(patch.object(scan_cmd, "classify_email", Mock(return_value=self.classification_result)))
        self.stack.enter_context(patch.object(scan_cmd.asyncio, "sleep", AsyncMock()))
        self.stack.enter_context(patch.object(scan_cmd.users, "update_last_scanned", Mock()))
        self.stack.enter_context(
            patch.object(scan_cmd.tasks_db, "find_or_create_application_for_linking", self.link_application)
        )
        self.stack.enter_context(patch.object(scan_cmd.tasks_db, "get_root_application_id", Mock(return_value=None)))
        self.stack.enter_context(patch.object(scan_cmd.tasks_db, "get_latest_chain_stage", Mock(return_value=None)))
        self.stack.enter_context(patch.object(scan_cmd.tasks_db, "find_existing_interview", self.find_existing_interview))
        self.stack.enter_context(patch.object(scan_cmd.tasks_db, "count_interviews_in_chain", self.count_interviews))
        self.stack.enter_context(patch.object(scan_cmd.tasks_db, "insert_task", self.insert_task))
        self.stack.enter_context(patch.object(scan_cmd.tasks_db, "update_interview_task", self.update_interview))
        self.stack.enter_context(patch.object(scan_cmd.tasks_db, "ensure_interview_chain", Mock(return_value=10)))
        return self

    def __exit__(self, exc_type, exc, tb):
        return self.stack.__exit__(exc_type, exc, tb)


class ScanInterviewSubtypeTests(unittest.IsolatedAsyncioTestCase):
    def test_normalises_known_subtypes_and_aliases(self):
        cases = {
            "invitation": "invitation",
            "invite": "invitation",
            "scheduling": "scheduling",
            "rescheduling": "scheduling",
            "reschedule": "scheduling",
            "confirmation": "confirmation",
            "confirmed": "confirmation",
            "scheduled": "confirmation",
            "prep": "unknown",
            None: "unknown",
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(scan_cmd._normalise_email_subtype(raw), expected)

    async def test_irrelevant_email_is_skipped_without_db_write(self):
        insert_task = Mock()
        link_application = Mock()

        with ScanPatch(
            {
                "type": "irrelevant",
                "company": "Acme",
                "role": "Software Engineer",
                "confidence": 0.95,
                "email_subtype": "unknown",
            },
            insert_task=insert_task,
            link_application=link_application,
        ):
            await self._run_scan()

        insert_task.assert_not_called()
        link_application.assert_not_called()

    async def test_unknown_interview_subtype_is_skipped_without_creating_fake_round(self):
        insert_task = Mock()
        link_application = Mock()
        count_interviews = Mock()

        with ScanPatch(
            {
                "type": "interview",
                "company": "Acme",
                "role": "Software Engineer",
                "confidence": 0.91,
                "interview_round": None,
                "is_final_round": 0,
                "round_label": None,
                "interview_date": None,
                "interview_platform": None,
                "email_subtype": "unknown",
            },
            insert_task=insert_task,
            link_application=link_application,
            count_interviews=count_interviews,
        ):
            await self._run_scan()

        insert_task.assert_not_called()
        link_application.assert_not_called()
        count_interviews.assert_not_called()

    async def test_interview_invitation_infers_first_round_and_creates_task(self):
        insert_task = Mock(return_value=99)
        count_interviews = Mock(return_value=0)

        with ScanPatch(
            {
                "type": "interview",
                "company": "Acme",
                "role": "Software Engineer",
                "deadline": None,
                "link": "https://meet.example.com/acme",
                "confidence": 0.96,
                "interview_round": None,
                "is_final_round": 0,
                "round_label": "technical",
                "interview_date": "2026-01-05T02:00:00Z",
                "interview_platform": "Google Meet",
                "email_subtype": "invitation",
            },
            insert_task=insert_task,
            count_interviews=count_interviews,
        ):
            await self._run_scan()

        count_interviews.assert_called_once_with(10)
        insert_task.assert_called_once()
        args, kwargs = insert_task.call_args
        self.assertEqual(args[:5], (123, "gmail-1", "interview", "Acme", "Software Engineer"))
        self.assertIsNone(args[5])
        self.assertEqual(args[7], 10)
        self.assertEqual(kwargs["cycle_id"], 42)
        self.assertEqual(kwargs["interview_round"], 1)
        self.assertEqual(kwargs["round_label"], "technical")
        self.assertEqual(kwargs["interview_date"], "2026-01-05T02:00:00Z")
        self.assertEqual(kwargs["interview_platform"], "Google Meet")
        self.assertIsNone(kwargs["confirmed_at"])

    async def test_scheduling_email_without_confirmed_time_creates_unscheduled_task(self):
        insert_task = Mock(return_value=99)

        with ScanPatch(
            {
                "type": "interview",
                "company": "Acme",
                "role": "Software Engineer",
                "deadline": "2026-01-03T00:00:00Z",
                "link": "https://calendar.example.com/acme",
                "confidence": 0.94,
                "interview_round": 1,
                "is_final_round": 0,
                "round_label": "phone screen",
                "interview_date": None,
                "interview_platform": None,
                "email_subtype": "scheduling",
            },
            insert_task=insert_task,
        ):
            await self._run_scan()

        insert_task.assert_called_once()
        args, kwargs = insert_task.call_args
        self.assertEqual(args[:5], (123, "gmail-1", "interview", "Acme", "Software Engineer"))
        self.assertIsNone(args[5])
        self.assertEqual(args[7], 10)
        self.assertEqual(kwargs["interview_round"], 1)
        self.assertEqual(kwargs["round_label"], "phone screen")
        self.assertIsNone(kwargs["interview_date"])
        self.assertIsNone(kwargs["interview_platform"])
        self.assertIsNone(kwargs["confirmed_at"])

    async def test_trackable_rescheduling_alias_still_creates_interview_task(self):
        insert_task = Mock(return_value=99)

        with ScanPatch(
            {
                "type": "interview",
                "company": "Acme",
                "role": "Software Engineer",
                "deadline": "2026-01-03T00:00:00Z",
                "link": "https://calendar.example.com/acme",
                "confidence": 0.92,
                "interview_round": 1,
                "is_final_round": 0,
                "round_label": "technical",
                "interview_date": None,
                "interview_platform": None,
                "email_subtype": "rescheduling",
            },
            insert_task=insert_task,
        ):
            await self._run_scan()

        insert_task.assert_called_once()
        args, kwargs = insert_task.call_args
        self.assertEqual(args[:5], (123, "gmail-1", "interview", "Acme", "Software Engineer"))
        self.assertIsNone(args[5])
        self.assertEqual(args[7], 10)
        self.assertEqual(kwargs["cycle_id"], 42)
        self.assertEqual(kwargs["interview_round"], 1)
        self.assertEqual(kwargs["round_label"], "technical")
        self.assertIsNone(kwargs["interview_date"])
        self.assertIsNone(kwargs["confirmed_at"])

    async def test_confirmation_updates_existing_interview_instead_of_inserting(self):
        existing_interview = {
            "id": 88,
            "gmail_id": "old-gmail",
            "source_application_id": 10,
            "interview_round": 1,
            "is_final_round": 0,
            "round_label": "technical",
        }
        insert_task = Mock()
        update_interview = Mock()

        with ScanPatch(
            {
                "type": "interview",
                "company": "Acme",
                "role": "Software Engineer",
                "deadline": None,
                "link": "https://meet.example.com/acme",
                "confidence": 0.97,
                "interview_round": None,
                "is_final_round": 0,
                "round_label": None,
                "interview_date": "2026-01-05T02:00:00Z",
                "interview_platform": "Google Meet",
                "email_subtype": "confirmation",
            },
            insert_task=insert_task,
            update_interview=update_interview,
            find_existing_interview=Mock(side_effect=[existing_interview, existing_interview]),
        ):
            await self._run_scan()

        insert_task.assert_not_called()
        update_interview.assert_called_once()
        args, kwargs = update_interview.call_args
        self.assertEqual(args[0], 88)
        self.assertEqual(kwargs["gmail_id"], "gmail-1")
        self.assertEqual(kwargs["interview_round"], 1)
        self.assertEqual(kwargs["interview_date"], "2026-01-05T02:00:00Z")
        self.assertEqual(kwargs["interview_platform"], "Google Meet")
        self.assertEqual(kwargs["confirmed_at"], "2026-01-02 10:00:00")

    async def _run_scan(self):
        await scan_cmd._run_scan(
            FakeBot(),
            123,
            _user(),
            scan_started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            scan_mode="manual",
        )


if __name__ == "__main__":
    unittest.main()
