import os
import unittest
from unittest.mock import patch
from tools import pr_releases


class ReleaseEventsTest(unittest.TestCase):
    def test_fork_pr_number_never_queries_upstream(self):
        environment = dict(SOURCE_REPO='Corax34/ucp_recorder',
                           GITHUB_REPOSITORY='Krarilotus/ucp_recorder',
                           GITHUB_EVENT_NAME='pull_request_target', REQUESTED_PR='2')
        with patch.dict(os.environ, environment), patch.object(pr_releases, 'gh') as gh, \
                patch.object(pr_releases, 'output') as output:
            pr_releases.discover()
            gh.assert_not_called()
            output.assert_called_once_with(builds={'include': []}, tests={'include': []}, count=0)

    def test_manual_release_requires_explicit_upstream_pr(self):
        environment = dict(SOURCE_REPO='Corax34/ucp_recorder',
                           GITHUB_REPOSITORY='Krarilotus/ucp_recorder',
                           GITHUB_EVENT_NAME='workflow_dispatch', REQUESTED_PR='')
        with patch.dict(os.environ, environment), patch.object(pr_releases, 'gh') as gh:
            with self.assertRaisesRegex(ValueError, 'upstream PR'):
                pr_releases.discover()
            gh.assert_not_called()
