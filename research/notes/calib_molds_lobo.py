import sys, glob, json, statistics, math
sys.path.insert(0, '/tmp/ns61/package/python')
from inksoul.molds import MOLDS, _KEYS, han_count

BOOKS = sorted(glob.glob('/sdcard/Project/InkSoul/experiment/corpus/human/*.txt'))

def segs_of(path, limit=200000):
    t = open(path, encoding='utf-8', errors='ignore').read()[:limit]
    out = []
    for i in range(0, len(t) - 1000, 1000):
        s = t[i:i+1000]
        if han_count(s) >= 600:
            out.append(s)
    return out

# per-segment densities
data = {b: [] for b in BOOKS}
for b in BOOKS:
    for s in segs_of(b):
        n = han_count(s)
        row = {}
        for m in MOLDS:
            row[m.key] = len(_KEYS[m.key].findall(s)) / n * 1000
        data[b].append(row)

keys = [m.key for m in MOLDS if m.direction in ('over','under')]
print('items judged:', len(keys))

def fit(train_rows):
    st = {}
    for k in keys:
        xs = [r[k] for r in train_rows]
        st[k] = (statistics.mean(xs), statistics.pstdev(xs) or 1e-9,
                 sorted(xs)[int(0.90*len(xs))], sorted(xs)[int(0.10*len(xs))])
    return st

def score(row, st):
    zsum = 0.0
    for k in keys:
        mu, sd, p90, p10 = st[k]
        d = MOLDS and dict((m.key, m.direction) for m in MOLDS)[k]
        z = (row[k] - mu) / sd
        zsum += max(0.0, z) if d == 'over' else max(0.0, -z)
    return zsum / len(keys)

# leave-one-book-out
fpr_peritem = []; fpr_composite = []; nseg = 0
all_z = []
for held in BOOKS:
    train = [r for b in BOOKS if b != held for r in data[b]]
    st = fit(train)
    train_z = sorted(score(r, st) for r in train)
    cutoff95 = train_z[int(0.95*len(train_z))]
    for r in data[held]:
        nseg += 1
        over = sum(1 for k in keys if MOLDS and dict((m.key, m.direction) for m in MOLDS)[k]=='over' and r[k] > st[k][2])
        under = sum(1 for k in keys if MOLDS and dict((m.key, m.direction) for m in MOLDS)[k]=='under' and r[k] < st[k][3])
        fpr_peritem.append(1 if (over or under) else 0)
        fpr_composite.append(1 if score(r, st) > cutoff95 else 0)

print('held-out human segments:', nseg)
print('A) 逐项 p90/p10 veto  -> human FAIL rate %.1f%%' % (100*sum(fpr_peritem)/nseg))
print('B) composite z > p95   -> human FAIL rate %.1f%%' % (100*sum(fpr_composite)/nseg))

# fit on all books, score AI drafts
st = fit([r for b in BOOKS for r in data[b]])
allz = sorted(score(r, st) for b in BOOKS for r in data[b])
c95 = allz[int(0.95*len(allz))]
man = json.load(open('/tmp/q6b/q6b_manifest.json'))
print()
print('AI 单篇 composite z（人类 p95 cutoff = %.2f）' % c95)
for it in man['items']:
    line = ['g%d' % it['idx']]
    for label, arm in it['mapping'].items():
        t = open(it['files'][label], encoding='utf-8').read()
        n = han_count(t)
        row = {m.key: len(_KEYS[m.key].findall(t))/n*1000 for m in MOLDS}
        line.append('%s:z=%.2f%s' % (arm, score(row, st), '*' if score(row, st) > c95 else ''))
    print(' '.join(line))
