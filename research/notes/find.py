#!/usr/bin/env python3
"""OpenAlex 主题检索: python3 find.py [--from 2023] "query" ... 输出紧凑候选列表"""
import sys, json, urllib.parse, urllib.request, time
UA={"User-Agent":"InkSoul-research/1.0 (mailto:research@example.org)"}
def get(u): return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=45).read().decode("utf-8","replace")
args=sys.argv[1:]; yr=None; n=6
if args and args[0]=="--from": yr=args[1]; args=args[2:]
for q in args:
    u="https://api.openalex.org/works?search=%s&per_page=%d&select=title,doi,publication_year,primary_location,cited_by_count,type"%(urllib.parse.quote(q),n)
    if yr: u+="&filter=from_publication_date:%s-01-01"%yr
    try: d=json.loads(get(u))
    except Exception as e: print("ERR",q,e); continue
    print("\n### QUERY:",q)
    for w in d.get("results",[]):
        src=((w.get("primary_location") or {}).get("source") or {})
        print(" - %s (%s) | %s | %s | cites=%s | %s"%(w.get("title"),w.get("publication_year"),src.get("display_name"),(w.get("doi") or "").replace("https://doi.org/",""),w.get("cited_by_count"),w.get("type")))
    time.sleep(0.3)
