"""Reuse the existing authenticated tunnel and exactly-once delivery code."""
import argparse
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'edge_linux_preflight_deployment_v1_20261103'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


client = load('client', OLD / 'client.py')
client.HERE = HERE
pipeline = load('_edge_repair_pipeline', OLD / 'pipeline.py')
pipeline.HERE = HERE
original_progress = pipeline.progress


def progress(stage, **fields):
    if stage == 'HPC_PREFLIGHT':
        replay = (fields.get('worker') or {}).get('replay')
        if replay:
            fields['message'] = ('原包重放：%s，第 %s 帧；已保存 %s 个端点；累计 %.1f 秒。'
                % (replay.get('role'), replay.get('frame', 0),
                   replay.get('selected_persisted', 0), replay.get('elapsed_seconds', 0)))
        else:
            fields['message'] = '预检排队或运行中；仅这一次有界作业，不自动重投。'
    original_progress(stage, **fields)
    # Keep the user's existing URL. This is a live presentation, not the old
    # job's sealed receipts; those remain in their original namespace.
    client.write(OLD / 'PROGRESS.json', dict(pipeline.record,
                 active_deployment=HERE.name, prior_failed_job_id='181403'))


pipeline.progress = progress


def bound_request(route, *args, **kwargs):
    value = client.request(route, *args, **kwargs)
    if route == 'state':
        spec = client.read(HERE / 'DELIVERY.json')
        client.need(value.get('receiver_source_sha256') == spec['receiver_source_sha256']
                    and value.get('repair_namespace') == HERE.name
                    and value.get('prior_job_id') == '181403', 'REPAIR_RECEIVER_IDENTITY')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--observe-seconds', type=int, default=1800)
    args = parser.parse_args()
    raise SystemExit(pipeline.run(observe_seconds=args.observe_seconds, action=bound_request))
