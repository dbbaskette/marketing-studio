"""Disposable GitHub boundary; all transport is local and no account is touched."""
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/blog-studio/scripts'
if str(SCRIPTS) not in sys.path:sys.path.insert(0, str(SCRIPTS))
from hub import Registry
import hub_store as store

class FakeProvider:
    def __init__(self, root):
        self.root = Path(root);self.root.mkdir(parents=True, exist_ok=True)
        self.repos = {};self.created = 0;self.review = False;self.unavailable = False
        self.timeout_after_create = False;self.prs = {}
    def lookup(self, repository):
        if self.unavailable:raise store.TransportError('Fixture offline; saved work is retained.')
        value = self.repos.get(repository)
        return dict(value) if value else None
    def create(self, repository, hub_id):
        self.created += 1
        if repository in self.repos:raise store.HubError('Fixture repository exists.')
        path = self.root / ('remote-' + str(self.created) + '.git')
        store.git(path, 'init', '--bare', '--quiet', '--initial-branch=main')
        self.repos[repository] = {'id': self.created, 'repository': repository,
            'url': 'https://github.com/' + repository, 'private': True,
            'description': 'Blog Studio Team Hub ' + hub_id, 'write': True, 'path': str(path)}
        if self.timeout_after_create:
            self.timeout_after_create = False
            raise store.TransportError('Fixture response lost after creation.')
    def actor(self):return 'Fixture member'
    def transport(self, metadata):return self.repos[metadata['repository']]['path']
    def review_required(self, repository):return self.review
    def ensure_pr(self, repository, branch, title):
        key = (repository, branch)
        self.prs.setdefault(key, 'https://github.com/' + repository + '/pull/1')
        return self.prs[key]
    def merge_review(self, repository, branch):
        remote = self.transport({'repository': repository})
        commit = store.git(remote, 'rev-parse', 'refs/heads/' + branch).decode().strip()
        store.git(remote, 'update-ref', 'refs/heads/main', commit)
