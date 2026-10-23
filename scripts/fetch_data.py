"""
scripts/fetch_data.py — Download MIT-BIH Arrhythmia Database Records

Downloads standard records (100, 101, 103, 105) and optional extended records into data/mitbih/.
Skips files that are already present.
Provides actionable offline fallback instructions if network is unavailable.
"""

import os
import sys
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "mitbih")
os.makedirs(DATA_DIR, exist_ok=True)

STANDARD_RECORDS = ["100", "101", "103", "105"]
EXTENDED_RECORDS = [
    "200", "207", "208", "210", "214", "219", "221", "228", "232", "234"
]

def check_record_exists(rec_id):
    dat = os.path.join(DATA_DIR, f"{rec_id}.dat")
    hea = os.path.join(DATA_DIR, f"{rec_id}.hea")
    atr = os.path.join(DATA_DIR, f"{rec_id}.atr")
    return os.path.exists(dat) and os.path.exists(hea) and os.path.exists(atr)

def fetch_records(records):
    missing = [r for r in records if not check_record_exists(r)]
    if not missing:
        print(f"[DATA] All {len(records)} records are already present in {DATA_DIR}.")
        return True

    print(f"[DATA] Attempting to download {len(missing)} missing records: {', '.join(missing)}...")
    try:
        import wfdb
        for r in missing:
            print(f"  Downloading record {r}...")
            wfdb.dl_database("mitdb", dl_dir=DATA_DIR, records=[r])
            if check_record_exists(r):
                print(f"  --> Record {r} downloaded successfully.")
            else:
                raise RuntimeError(f"Download of {r} failed to write complete files.")
        return True
    except Exception as e:
        print("\n" + "="*70)
        print("ERROR: Failed to download dataset records over network:")
        print(f"  {e}")
        print("\nOFFLINE MANUAL INSTRUCTIONS:")
        print(f"  1. Download the MIT-BIH Arrhythmia Database (.dat, .hea, .atr files) from:")
        print("     https://physionet.org/content/mitdb/1.0.0/")
        print(f"  2. Place files into: {DATA_DIR}")
        print("     Example: 100.dat, 100.hea, 100.atr")
        print("="*70 + "\n")
        return False

def main():
    parser = argparse.ArgumentParser(description="Fetch MIT-BIH dataset records")
    parser.add_argument("--extended", action="store_true", help="Also download extended records")
    args = parser.parse_args()

    recs = STANDARD_RECORDS.copy()
    if args.extended:
        recs.extend(EXTENDED_RECORDS)

    ok = fetch_records(recs)
    if not ok:
        # Check if at least standard records are present
        if all(check_record_exists(r) for r in STANDARD_RECORDS):
            print("[DATA] Standard records (100, 101, 103, 105) are present. Standard flow can proceed.")
            sys.exit(0)
        else:
            sys.exit(1)

if __name__ == "__main__":
    main()
