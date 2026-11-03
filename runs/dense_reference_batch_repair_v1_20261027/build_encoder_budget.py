"""Local preparation only: exact sealed reference batching budget, zero forwards."""
import argparse
import json
from pathlib import Path
from encoder_adapter import build_budget, canonical, require


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen-root',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();output=Path(args.output)
    require(not output.exists(),'NEW_PHYSICAL_BUDGET_OUTPUT_REQUIRED')
    budget=build_budget(args.frozen_root)
    with output.open('xb') as stream:stream.write(canonical(budget)+b'\n')
    print(json.dumps(dict(status='PREPARED_NOT_EXECUTED',totals=budget['totals'],
                         real_forwards=0,target_query_inputs=0),sort_keys=True))


if __name__=='__main__':main()
