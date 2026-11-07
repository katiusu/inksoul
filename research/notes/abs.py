#!/usr/bin/env python3
"""按 DOI / 标题 取 OpenAlex 摘要与元数据。用法: python3 abs.py "doi:10.1073/pnas.xxx" "标题..." """
import sys, json, urllib.parse, urllib.request, time
UA={"User-Agent":"InkSoul-research/1.0 (mailto:research@example.org)"}
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=45).read().decode("utf-8","replace")
def abstract_from_inv(inv):
    if not inv: return ""
    pos=[]
    for w,ids in inv.items():
        for i in ids: pos.append((i,w))
    return " ".join(w for _,w in sorted(pos))
def show(q):
    if q.startswith("doi:"):
        d=json.loads(get("https://api.openalex.org/works/https://doi.org/"+urllib.parse.quote(q[4:])))
    else:
        d=json.loads(get("https://api.openalex.org/works?search=%s&per_page=1"%urllib.parse.quote(q)))["results"][0]
    src=((d.get("primary_location") or {}).get("source") or {})
    print("="*100)
    print("TITLE:",d.get("title"))
    print("YEAR:",d.get("publication_year"),"| VENUE:",src.get("display_name"),"| TYPE:",d.get("type"),"| CITED:",d.get("cited_by_count"))
    print("DOI:",d.get("doi"))
    print("AUTHORS:",", ".join(a["author"]["display_name"] for a in d.get("authorships",[])[:8]))
    print("ABSTRACT:",abstract_from_inv(d.get("abstract_inverted_index"))[:2600])
for q in sys.argv[1:]:
    try: show(q)
    except Exception as e: print("ERR",q,e)
    time.sleep(0.3)
