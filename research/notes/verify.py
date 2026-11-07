#!/usr/bin/env python3
"""引文核实工具：对给定标题批量查询 OpenAlex / Crossref / arXiv，输出可核验记录。
用法: python3 verify.py "Title 1" "Title 2" ...  或  python3 verify.py --file titles.txt
"""
import sys, json, time, urllib.parse, urllib.request

UA = {"User-Agent": "InkSoul-research/1.0 (mailto:research@example.org)"}

def _get(url, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def openalex(title, n=3):
    u = "https://api.openalex.org/works?search=%s&per_page=%d&select=id,doi,title,publication_year,primary_location,authorships,cited_by_count,type" % (urllib.parse.quote(title), n)
    try:
        d = json.loads(_get(u))
    except Exception as e:
        return {"error": str(e)}
    out = []
    for w in d.get("results", []):
        loc = w.get("primary_location") or {}
        src = (loc.get("source") or {}) if isinstance(loc.get("source"), dict) else {}
        out.append({
            "title": w.get("title"), "year": w.get("publication_year"),
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "venue": src.get("display_name"), "type": w.get("type"),
            "cited_by": w.get("cited_by_count"),
            "authors": [a["author"]["display_name"] for a in (w.get("authorships") or [])][:8],
        })
    return out

def crossref(title, n=2):
    u = "https://api.crossref.org/works?query.bibliographic=%s&rows=%d&select=title,DOI,issued,container-title,author,type" % (urllib.parse.quote(title), n)
    try:
        d = json.loads(_get(u))
    except Exception as e:
        return {"error": str(e)}
    out = []
    for it in d.get("message", {}).get("items", []):
        out.append({
            "title": (it.get("title") or [""])[0], "doi": it.get("DOI"),
            "year": (it.get("issued", {}).get("date-parts") or [[None]])[0][0],
            "venue": (it.get("container-title") or [""])[0], "type": it.get("type"),
            "authors": [" ".join(filter(None, [a.get("given"), a.get("family")])) for a in (it.get("author") or [])][:8],
        })
    return out

def arxiv(title, n=3):
    u = "https://export.arxiv.org/api/query?search_query=ti:%s&max_results=%d" % (urllib.parse.quote('"%s"' % title), n)
    try:
        x = _get(u)
    except Exception as e:
        return {"error": str(e)}
    import re
    ents = re.findall(r"<entry>(.*?)</entry>", x, re.S)
    out = []
    for e in ents:
        g = lambda tag: (re.search(r"<%s>(.*?)</%s>" % (tag, tag), e, re.S) or [None, None])[1]
        t = (g("title") or "").strip().replace("\n", " ")
        out.append({"title": " ".join(t.split()), "arxiv_id": (g("id") or "").split("/abs/")[-1],
                    "published": (g("published") or "")[:10],
                    "authors": re.findall(r"<name>(.*?)</name>", e)[:8]})
    return out

def main():
    args = sys.argv[1:]
    titles = []
    i = 0
    while i < len(args):
        if args[i] == "--file":
            titles += [l.strip() for l in open(args[i+1], encoding="utf-8") if l.strip()]
            i += 2
        else:
            titles.append(args[i]); i += 1
    for t in titles:
        print("=" * 100)
        print("QUERY:", t)
        for name, fn in (("OPENALEX", openalex), ("CROSSREF", crossref), ("ARXIV", arxiv)):
            r = fn(t)
            print(" %s: %s" % (name, json.dumps(r, ensure_ascii=False)[:1400]))
            time.sleep(0.4)

if __name__ == "__main__":
    main()
