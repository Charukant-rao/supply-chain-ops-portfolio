# Generates a synthetic (sample) warehouse dataset for a fictional D2C brand, 1 facility, 28 days.
import random, csv, datetime as dt
random.seed(42)
start = dt.date(2026, 9, 28)  # 28 days: Sep 28 - Oct 25, 2026
channels = [("Website", 0.40), ("Amazon", 0.30), ("Flipkart", 0.18), ("Myntra", 0.12)]
cats = [("Apparel", 0.45), ("Footwear", 0.20), ("Accessories", 0.20), ("Home", 0.15)]
skus = {c: [f"{c[:3].upper()}-{i:03d}" for i in range(1, 41)] for c, _ in cats}
# failure step causing a missed dispatch SLA, with relative weight
fail_steps = [("Inventory sync", 0.24), ("Allocation", 0.20), ("Invoice", 0.18), ("Label / AWB", 0.17),
              ("Short pick", 0.11), ("Manifest", 0.06), ("E-way bill", 0.04)]
def pick(opts):
    r = random.random(); acc = 0
    for v, w in opts:
        acc += w
        if r <= acc: return v
    return opts[-1][0]

PROBLEM = {"HOM-007": "Invoice", "FOO-021": "Short pick", "APP-031": "Allocation"}
orders, picks, counts = [], [], []
oid = 100000
for d in range(28):
    day = start + dt.timedelta(days=d)
    wd = day.weekday()
    base = 1150 + (350 if wd in (0, 1) else 0) - (200 if wd == 6 else 0)
    # sale spike days 10-12 (festive sale)
    if 10 <= d <= 12: base = int(base * 1.9)
    n = int(base * random.uniform(0.92, 1.08))
    # missed-SLA rate rises in sale days and on an AWB outage day (d=18)
    p_miss = 0.035 + (0.06 if 10 <= d <= 12 else 0) + (0.05 if d == 18 else 0)
    for _ in range(n):
        oid += 1
        ch = pick(channels); cat = pick(cats); sku = random.choice(skus[cat])
        shift = "Morning" if random.random() < 0.58 else "Evening"
        prob = PROBLEM.get(sku)
        miss = random.random() < (p_miss + (0.14 if prob else 0)) * (1.35 if shift == "Evening" else 1.0) * (1.4 if ch == "Flipkart" else 1)
        step = ""
        if miss:
            if prob and random.random() < 0.8: step = prob
            elif d == 18 and random.random() < 0.7: step = "Label / AWB"
            elif 10 <= d <= 12 and random.random() < 0.45: step = "Inventory sync"
            else: step = pick(fail_steps)
        # dispatch SLA = carrier pickup within 24 h of order creation
        tat = min(23.8, max(2.0, random.gauss(9.5, 3.0))) if not miss else max(24.3, random.gauss(32, 8))
        tat = round(tat, 1)
        orders.append(dict(order_id=f"SO{oid}", date=day.isoformat(), channel=ch, category=cat, sku=sku,
                           shift=shift, tat_hours=tat, sla_met=0 if miss else 1, failure_step=step))
    # pick lines for the day
    lines = int(n * 1.6)
    p_err = 0.006 + (0.006 if 10 <= d <= 12 else 0)
    for sh in ("Morning", "Evening"):
        l = int(lines * (0.58 if sh == "Morning" else 0.42))
        e = sum(1 for _ in range(l) if random.random() < p_err * (1.5 if sh == "Evening" else 1))
        picks.append(dict(date=day.isoformat(), shift=sh, pick_lines=l, pick_errors=e))
    # cycle count: 60 bins/day
    for _ in range(60):
        cat = pick(cats); sku = random.choice(skus[cat])
        sys_q = random.randint(5, 80)
        r = random.random()
        diff = 0 if r < 0.93 else random.choice([-3, -2, -1, -1, 1, 2])
        counts.append(dict(date=day.isoformat(), sku=sku, category=cat, system_qty=sys_q,
                           physical_qty=max(0, sys_q + diff), mismatch=1 if diff else 0))

def w(name, rows):
    with open(name, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys())); wr.writeheader(); wr.writerows(rows)
w("orders.csv", orders); w("picks.csv", picks); w("cycle_counts.csv", counts)
print(len(orders), len(picks), len(counts))
