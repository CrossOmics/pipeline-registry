import os
import subprocess
from datetime import datetime, timezone

import httpx
import pytest
import yaml

from helpers import REPO_ROOT, pipeline_doc, version_doc, write_registry
from registry_tools.citations import CitationCollector, OpenAlexClient, SemanticScholarClient
from registry_tools.collect import collect_metrics
from registry_tools.github import GitHubCollector
from registry_tools.http import CollectError, request_json
from registry_tools.index import build_index, serialize
from registry_tools.model import load_registry
from registry_tools.schema import load_schema
from registry_tools.validate import validate_registry
from test_collect import FakeCitations, FakeGitHub

NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize('field', ['value', 'baseline'])
@pytest.mark.parametrize('number', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_metrics_have_field_diagnostics(tmp_path, field, number):
    metric = {'name': 'rss', 'value': 1, field: number}
    write_registry(tmp_path, pipeline_doc(versions=[version_doc('cv_alpha_1'), version_doc(
        'cv_alpha_2', 'b', parent='cv_alpha_1', kind='optimization',
        improvement_effect={'metrics': [metric]})]))
    issues = validate_registry(load_registry(tmp_path), load_schema(REPO_ROOT))
    assert any(i.rule == 'R1' and i.pointer == '/versions/1/improvement_effect/metrics/0/' + field for i in issues)


def test_serializer_refuses_invalid_json_numbers():
    with pytest.raises(ValueError):
        serialize({'value': float('nan')})


@pytest.mark.parametrize('body', [b'<html>gateway</html>', b'[]', b'null'])
def test_bad_success_body_retries_and_becomes_collect_error(body):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=body)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CollectError):
            request_json(client, 'GET', 'https://x.test', sleep=lambda _: None)
    assert len(calls) == 4


@pytest.mark.parametrize('body', [{}, {'cited_by_count': 4, 'counts_by_year': [{}]},
                                  {'cited_by_count': 'broken', 'counts_by_year': []}])
def test_malformed_citation_success_keeps_other_pipelines(tmp_path, body):
    write_registry(tmp_path, pipeline_doc('cp_alpha'), pipeline_doc('cp_beta', papers=[]))
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)))
    citations = CitationCollector(OpenAlexClient(client, None), SemanticScholarClient(client), [2024, 2025, 2026])
    metrics, failed, attempted = collect_metrics(load_registry(tmp_path), None, FakeGitHub(), citations, NOW)
    assert (failed, attempted) == (1, 2)
    assert metrics['pipelines']['cp_alpha']['stale_since'] is not None
    assert metrics['pipelines']['cp_beta']['activity'] is not None


@pytest.mark.parametrize('body', [{'data': {'repository': []}}, {'data': {'repository': {'url': 'https://github.com/a/b'}}}])
def test_malformed_github_success_is_collect_error(body):
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)))
    with pytest.raises(CollectError):
        GitHubCollector(client, None, sleep=lambda _: None).collect('https://github.com/a/b', NOW)


@pytest.mark.parametrize('repositories,reason', [([], 'no_repo'),
    ([{'url': 'https://gitlab.com/a/b', 'primary': True}], 'unsupported_host'),
    ([{'url': 'https://github.com/new/repo', 'primary': True}], 'repo_unreachable')])
def test_primary_repo_changes_invalidate_collected_activity(tmp_path, repositories, reason):
    write_registry(tmp_path, pipeline_doc())
    metrics, _, _ = collect_metrics(load_registry(tmp_path), None, FakeGitHub(), FakeCitations(), NOW)
    write_registry(tmp_path, pipeline_doc(repositories=repositories))
    entry = build_index(load_registry(tmp_path), metrics, 'f' * 40, NOW)['pipelines'][0]['metrics']
    assert entry['activity'] is None
    assert entry['priority'] is None
    assert entry['priority_reason'] == reason


def test_collection_binds_activity_to_normalized_primary(tmp_path):
    write_registry(tmp_path, pipeline_doc(repositories=[{'url': 'https://github.com/ORG/Alpha.git/', 'primary': True}]))
    metrics, _, _ = collect_metrics(load_registry(tmp_path), None, FakeGitHub(), FakeCitations(), NOW)
    assert metrics['pipelines']['cp_alpha']['activity_repository'] == 'https://github.com/org/alpha'
    write_registry(tmp_path, pipeline_doc())
    assert build_index(load_registry(tmp_path), metrics, 'f' * 40, NOW)['pipelines'][0]['metrics']['priority'] is not None


@pytest.mark.parametrize('failure', ['fetch', 'show'])
def test_deploy_step_stops_when_metrics_cannot_be_read(tmp_path, failure):
    workflow = yaml.safe_load((REPO_ROOT / '.github/workflows/build.yml').read_text())
    script = next(step['run'] for step in workflow['jobs']['build']['steps'] if step.get('name') == 'Fetch the last collected metrics')
    git = tmp_path / 'git'
    git.write_text('#!/bin/sh\nif [ "$1" = "$FAIL_OPERATION" ]; then exit 1; fi\nexit 0\n')
    git.chmod(0o755)
    result = subprocess.run(['bash', '-e', '-c', script], cwd=tmp_path,
        env={**os.environ, 'PATH': str(tmp_path) + ':' + os.environ['PATH'], 'FAIL_OPERATION': failure}, capture_output=True)
    assert result.returncode != 0


def test_bwa_mem2_uses_its_evidenced_baseline():
    registry = load_registry(REPO_ROOT)
    bwa = next(p for p in registry.pipelines() if p['id'] == 'cp_bwa')
    versions = {v['id']: v for v in bwa['versions']}
    optimized = next(v for v in versions.values() if v['repo'] == 'https://github.com/bwa-mem2/bwa-mem2')
    baseline = versions[optimized['parent']]
    assert baseline['commit'] == '9f26bfcc7780753129b60717ecab0ebba6f04b7c'
    assert baseline['released_at'] < optimized['released_at']
    scanpy = next(p for p in registry.pipelines() if p['id'] == 'cp_scanpy')
    assert all(v['kind'] == 'original' for v in scanpy['versions'])
