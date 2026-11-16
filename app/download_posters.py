import argparse
import csv
import difflib
import json
import math
import os
import re
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Chạy: python app/download_posters.py (từ thư mục gốc dự án hoặc bất kỳ thư mục nào)
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.utils.ConfigUtil import ConfigUtil

# Tải sẵn poster của toàn bộ phim từ TMDB vào thư mục posters/ (cùng thư mục, cùng tên file <movie_id>.jpg và
# cùng posters/not_found.txt mà app/utils/TmdbUtil.py dùng) để giao diện không phải tải từng phim khi người dùng xem.
# Cần API key của TMDB: --key, biến môi trường TMDB_API_KEY, hoặc config.json mục tmdb > api_key.
#   python app/download_posters.py --limit 20     # chạy thử 20 phim đầu
#   python app/download_posters.py                # tải tất cả (khoảng 3.900 phim, vài phút); chạy lại sẽ bỏ qua phim đã có
#   python app/download_posters.py --force        # tìm lại + chấm điểm lại tất cả; ảnh chỉ tải lại khi poster được chọn đổi
#                                                 # hoặc phim chưa có trong tmdb_map.csv
#   python app/download_posters.py --retry-missing   # tìm lại cả các phim đã được ghi là không có poster
#   python app/download_posters.py --no-images    # chỉ tìm + chấm điểm, ghi poster_path vào tmdb_map.csv, KHÔNG tải ảnh
# Dừng giữa chừng (Ctrl+C) an toàn: file ảnh được ghi trọn vẹn từng cái, chạy lại sẽ làm tiếp từ chỗ dở.
#
# Chọn phim TMDB cho mỗi phim MovieLens: không lấy kết quả tìm kiếm đầu tiên mà chấm điểm từng ứng viên có poster
# (tối đa 100): năm phát hành (trùng 50, lệch 1 năm 35, lệch 2 năm 10, lệch hơn 2 năm -30; thiếu năm 20) + độ giống tên
# (0-40, so với tên chính và các tên phụ trong ngoặc của MovieLens; tên không có chữ Latin để so thì 8, nên chỉ đạt "review") + số lượt bình chọn
# (0-10, chỉ để phân thắng bại giữa các phim cùng tên).
#   điểm >= --review-score (70): nhận;  --min-score (40) đến 70: nhận nhưng đánh dấu "review" để xem lại;
#   dưới --min-score: không nhận (ghi "rejected", coi là không có poster; poster cũ của phim đó, nếu có, được chuyển sang posters/rejected/).
# Kết quả ghép từng phim ghi ở posters/tmdb_map.csv (movie_id, tmdb_id, tên/năm TMDB, poster_path, điểm, status) để kiểm tra lại.
# Có poster_path thì không cần lưu ảnh: ảnh mở được thẳng từ https://image.tmdb.org/t/p/w342<poster_path> (không cần API key).
API_URL="https://api.themoviedb.org/3"
IMAGE_URL="https://image.tmdb.org/t/p"
SIZES=("w92","w154","w185","w342","w500","w780","original")
folder_posters=ConfigUtil.rootPath(ConfigUtil.get("paths","poster_dir","posters"))
file_movies=ConfigUtil.rootPath("data/processed/cleaned_movies.csv")
file_not_found=os.path.join(folder_posters,"not_found.txt")
file_map=os.path.join(folder_posters,"tmdb_map.csv")
MAP_COLUMNS=("movie_id","title","year","tmdb_id","tmdb_title","tmdb_year","poster_path","score","status")
stop=threading.Event()      # đặt khi gặp lỗi key (401): các luồng không bắt đầu thêm việc mới


class AuthError(Exception):
    pass


def searchTitle(title):
    # Giống TmdbUtil.searchTitle: "City of Lost Children, The (Cité des enfants perdus, La) (1995)" -> "The City of Lost Children"
    t=re.sub(r"\s*\([^)]*\)","",str(title)).strip()
    for art in (", The", ", A", ", An", ", Les", ", La", ", Il", ", Le", ", L'", ", Das", ", Der", ", Die", ", El"):
        if t.endswith(art):
            t=art[2:]+("" if art.endswith("'") else " ")+t[:-len(art)]
            break
    return t
def posterPath(movie_id):
    return os.path.join(folder_posters,f"{int(movie_id)}.jpg")
def loadMovies(path):
    # [(movie_id, title, năm phát hành hoặc None)] theo thứ tự movie_id; năm lấy từ cột release_year, thiếu thì lấy từ tên phim
    movies={}
    with open(path,encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            try:
                movie_id=int(row["movie_id"])
            except (KeyError,ValueError):
                continue
            title=row.get("title") or ""
            try:
                year=int(float(row.get("release_year")))
            except (TypeError,ValueError,OverflowError):
                m=re.search(r"\((\d{4})\)\s*$",title)
                year=int(m.group(1)) if m else None
            movies.setdefault(movie_id,(movie_id,title,year))       # trùng movie_id thì lấy dòng đầu
    return [movies[k] for k in sorted(movies)]
def loadNotFound():
    if not os.path.exists(file_not_found):
        return set()
    return set(int(x) for x in open(file_not_found).read().split() if x.isdigit())
def saveNotFound(added,removed):
    # Đọc lại file ngay lúc ghi để giữ các id app (TmdbUtil) vừa thêm trong lúc script chạy; ghi trọn vẹn rồi mới đổi tên
    ids=(loadNotFound()-removed)|added
    os.makedirs(folder_posters,exist_ok=True)
    tmp=file_not_found+".part"
    with open(tmp,"w") as f:
        f.write("".join(f"{i}\n" for i in sorted(ids)))
    os.replace(tmp,file_not_found)
def loadMap():
    # {movie_id: dòng của tmdb_map.csv}
    rows={}
    if os.path.exists(file_map):
        with open(file_map,encoding="utf-8",newline="") as f:
            for row in csv.DictReader(f):
                if (row.get("movie_id") or "").isdigit():
                    rows[int(row["movie_id"])]=row
    return rows
def saveMap(new_rows):
    # Gộp với các dòng đã có (dòng mới đè dòng cũ cùng movie_id), sắp theo movie_id, ghi trọn vẹn rồi mới đổi tên
    rows=loadMap()
    rows.update(new_rows)
    os.makedirs(folder_posters,exist_ok=True)
    tmp=file_map+".part"
    with open(tmp,"w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=MAP_COLUMNS,extrasaction="ignore")
        writer.writeheader()
        for k in sorted(rows):
            writer.writerow(rows[k])
    os.replace(tmp,file_map)
def fetch(url,headers=None,retries=4):
    # GET có thử lại: 429 (quá giới hạn) chờ theo Retry-After (1-60 giây), lỗi mạng / 5xx chờ tăng dần;
    # 401 = sai key; 404 -> None; các lỗi 4xx khác không thử lại
    last=None
    for attempt in range(retries):
        wait=2**attempt
        if stop.is_set():
            raise AuthError("đã dừng")
        try:
            with urlopen(Request(url,headers=headers or {}),timeout=20) as reply:
                return reply.read()
        except HTTPError as e:
            if e.code==401:
                stop.set()
                raise AuthError("API key không hợp lệ (TMDB trả về 401)")
            if e.code==404:
                return None
            if e.code!=429 and e.code<500:
                raise RuntimeError(f"HTTP {e.code}")          # lỗi phía yêu cầu (400, 422...): thử lại cũng vô ích
            if e.code==429:
                try:
                    v=float(e.headers.get("Retry-After"))
                    if v==v:
                        wait=min(max(v,1.0),60.0)
                except (TypeError,ValueError):
                    pass
            last=f"HTTP {e.code}"
        except Exception as e:
            last=type(e).__name__
        if attempt<retries-1:
            time.sleep(wait)
    raise RuntimeError(f"lỗi mạng sau {retries} lần thử ({last})")
# ---------------- chấm điểm ứng viên ----------------
def normTitle(s):
    # chữ thường, bỏ dấu, "&" -> "and", chỉ giữ chữ-số ASCII: "Cité des enfants perdus" -> "cite des enfants perdus"
    s=unicodedata.normalize("NFKD",str(s).lower().replace("&"," and "))
    s="".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+"," ",s).split())
def queryTitles(title):
    # Tên chính và các tên phụ trong ngoặc của MovieLens (trừ năm), đã chuẩn hóa mạo từ và bỏ dấu
    names=[searchTitle(title)]
    for alt in re.findall(r"\(([^)]*)\)",str(title)):
        alt=alt.strip()
        if alt and not re.fullmatch(r"\d{4}",alt):
            names.append(searchTitle(alt))
    return [n for n in (normTitle(x) for x in names) if n]
def number(x):
    # số hữu hạn >= 0, còn lại (None, chuỗi, NaN, vô cực...) -> 0
    try:
        x=float(x)
    except (TypeError,ValueError):
        return 0.0
    return x if math.isfinite(x) and x>0 else 0.0
def scoreCandidate(c,queries,year):
    # -30..100: năm (-30..50) + độ giống tên (0-40) + lượt bình chọn (0-10)
    rd=str(c.get("release_date") or "")[:4]
    if year is None or not re.fullmatch(r"[0-9]{4}",rd):
        year_score=20
    else:
        year_score={0:50,1:35,2:10}.get(abs(int(rd)-year),-30)      # lệch hơn 2 năm: nhiều khả năng là phim khác cùng tên
    names=[normTitle(c.get("title") or ""),normTitle(c.get("original_title") or "")]
    pairs=[difflib.SequenceMatcher(None,q,t).ratio() for q in queries for t in names if q and t]
    sim=max(pairs) if pairs else 0.2         # tên không có chữ Latin để so (vd. tiếng Nhật): không đủ căn cứ, điểm tên trung tính 8 (tối đa 68: chỉ "review")
    return year_score+40*sim+min(math.log10(1+number(c.get("vote_count"))),4.0)*2.5
def searchBest(title,year,key,api_url,review_score):
    # (điểm, ứng viên) tốt nhất trong các kết quả có poster, hoặc None.
    # Tìm kèm năm trước; chưa có ứng viên đủ tin cậy thì tìm thêm không kèm năm (năm MovieLens đôi khi lệch 1 năm)
    headers={"Authorization":f"Bearer {key}"} if len(key)>40 else {}
    queries=queryTitles(title)
    candidates={}
    best=None
    for y in ((year,None) if year else (None,)):
        params={"query":searchTitle(title),"include_adult":"false","language":"en-US"}
        if y:
            params["year"]=y
        if len(key)<=40:       # API Key v3 gửi qua tham số, Read Access Token v4 gửi qua header
            params["api_key"]=key
        try:
            data=fetch(f"{api_url}/search/movie?{urlencode(params)}",headers)
        except AuthError:
            raise
        except Exception:
            if candidates:          # đã có ứng viên từ lần tìm trước: dùng tạm thay vì bỏ cả phim
                break
            raise
        if data is None:
            continue
        for c in json.loads(data.decode("utf-8")).get("results",[]):
            if c.get("poster_path") and c.get("id") not in candidates:
                candidates[c.get("id")]=c
        scored=[(scoreCandidate(c,queries,year),number(c.get("vote_count")),c) for c in candidates.values()]
        if scored:
            top=max(scored,key=lambda x:(x[0],x[1]))
            best=(top[0],top[2])
            if best[0]>=review_score:
                break
    return best
def downloadOne(movie_id,title,year,key,api_url,image_url,min_score,review_score,known,images=True):
    # Trả về (kết quả, dòng cho tmdb_map.csv hoặc None). Kết quả: "ok" / "review" (nhận nhưng điểm thấp) /
    # "missing" (không có ứng viên đủ điểm) / "stopped" (đã dừng do sai key, chưa làm gì).
    # Lỗi mạng, sai dữ liệu... ném ngoại lệ để không bị ghi nhầm là "không có poster".
    if stop.is_set():
        return "stopped",None
    best=searchBest(title,year,key,api_url,review_score)
    if best is None:
        return "missing",None
    score,c=best
    tmdb_year=str(c.get("release_date") or "")[:4]
    info={"movie_id":movie_id,"title":title,"year":year or "","tmdb_id":c.get("id"),"tmdb_title":c.get("title") or "",
          "tmdb_year":tmdb_year,"poster_path":c["poster_path"],"score":round(score,1)}
    path=posterPath(movie_id)
    if score<min_score:
        info["status"]="rejected"
        if os.path.exists(path):        # poster cũ (tải theo cách khác) nhiều khả năng sai phim: cất sang posters/rejected/
            try:
                os.makedirs(os.path.join(folder_posters,"rejected"),exist_ok=True)
                os.replace(path,os.path.join(folder_posters,"rejected",os.path.basename(path)))
            except OSError:             # file đang được mở (Windows): vẫn ghi nhận kết quả, lần chạy sau thử cất lại
                pass
        return "missing",info
    if stop.is_set():
        return "stopped",None
    if images and (known.get(movie_id)!=c["poster_path"] or not os.path.exists(path)):
        data=fetch(image_url+c["poster_path"])
        if data is None or data[:2]!=b"\xff\xd8":
            raise RuntimeError("TMDB không trả về ảnh JPEG")
        os.makedirs(folder_posters,exist_ok=True)
        tmp=path+".part"
        try:
            with open(tmp,"wb") as f:
                f.write(data)
            os.replace(tmp,path)   # ghi trọn vẹn rồi mới đổi tên, dừng giữa chừng không để lại ảnh hỏng
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
    info["status"]="ok" if score>=review_score else "review"
    return info["status"],info
def main(argv=None):
    for stream in (sys.stdout,sys.stderr):      # console Windows mặc định cp1252 không in được tiếng Việt khi bị chuyển hướng
        if hasattr(stream,"reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap=argparse.ArgumentParser(description="Tải poster phim từ TMDB vào thư mục posters/")
    ap.add_argument("--key",help="API key v3 hoặc Read Access Token v4 (mặc định: TMDB_API_KEY hoặc config.json)")
    ap.add_argument("--movies",default=file_movies,help="CSV có cột movie_id,title,release_year (mặc định: data/processed/cleaned_movies.csv)")
    ap.add_argument("--size",default="w342",choices=SIZES,help="cỡ ảnh (mặc định w342, cùng cỡ app dùng)")
    ap.add_argument("--workers",type=int,default=4,help="số luồng tải song song, 1-10 (mặc định 4)")
    ap.add_argument("--limit",type=int,default=0,help="chỉ xử lý N phim đầu (0 = tất cả), dùng để chạy thử")
    ap.add_argument("--force",action="store_true",help="tìm lại và chấm điểm lại cả phim đã có poster (và phim đã ghi là không có poster); "
                    "ảnh chỉ tải lại khi poster được chọn khác lần trước hoặc phim chưa có trong tmdb_map.csv")
    ap.add_argument("--retry-missing",action="store_true",help="tìm lại cả các phim đã được ghi là không có poster")
    ap.add_argument("--no-images",action="store_true",help="chỉ tìm và chấm điểm, ghi poster_path vào tmdb_map.csv, không tải ảnh "
                    "(ảnh mở thẳng từ image.tmdb.org/t/p/<cỡ><poster_path>)")
    ap.add_argument("--min-score",type=float,default=40.0,help="điểm tối thiểu để nhận ứng viên (mặc định 40)")
    ap.add_argument("--review-score",type=float,default=70.0,help="dưới điểm này nhưng đủ --min-score: nhận và đánh dấu review (mặc định 70)")
    ap.add_argument("--api-url",default=API_URL,help="địa chỉ API TMDB; nếu máy không phân giải được api.themoviedb.org "
                    "(một số nhà mạng chặn) dùng https://api.tmdb.org/3")
    ap.add_argument("--image-url",default=IMAGE_URL,help=argparse.SUPPRESS)
    args=ap.parse_args(argv)
    stop.clear()
    key=(args.key or os.environ.get("TMDB_API_KEY") or ConfigUtil.get("tmdb","api_key","") or "").strip()
    if key=="":
        print("Chưa có API key TMDB. Đăng ký miễn phí tại https://www.themoviedb.org/settings/api rồi dùng --key, "
              "biến môi trường TMDB_API_KEY hoặc điền config.json mục tmdb > api_key.")
        return 1
    movies=loadMovies(args.movies)
    if args.limit>0:
        movies=movies[:args.limit]
    not_found=loadNotFound()
    mapped=loadMap()
    known={k:row.get("poster_path") for k,row in mapped.items() if row.get("status") in ("ok","review")}
    retry=args.force or args.retry_missing
    images=not args.no_images
    done=(lambda movie_id: movie_id in mapped) if args.no_images else (lambda movie_id: os.path.exists(posterPath(movie_id)))
    todo=[m for m in movies if (args.force or not done(m[0])) and (retry or m[0] not in not_found)]
    verb="tải được" if images else "ghép được"
    print(f"{len(movies)} phim: {len(movies)-len(todo)} bỏ qua (đã có {'poster' if images else 'trong tmdb_map.csv'} "
          f"hoặc đã biết không có), {len(todo)} cần {'tải' if images else 'ghép'}.")
    image_url=f"{args.image_url.rstrip('/')}/{args.size}"
    count={"ok":0,"review":0,"missing":0,"error":0}
    errors=[]
    added=set()         # phim mới biết là không có poster
    removed=set()       # phim đã tải được poster -> gỡ khỏi not_found.txt
    rows={}             # dòng mới cho tmdb_map.csv
    status=0
    start=time.time()
    executor=ThreadPoolExecutor(max_workers=min(max(args.workers,1),10))
    try:
        futures={executor.submit(downloadOne,m[0],m[1],m[2],key,args.api_url,image_url,args.min_score,args.review_score,known,images):m
                 for m in todo}
        for k,future in enumerate(as_completed(futures),1):
            movie_id=futures[future][0]
            try:
                result,info=future.result()
            except AuthError as e:
                if status==0:
                    print(f"Dừng: {e}. Kiểm tra lại API key.")
                    status=2
                continue
            except Exception as e:
                result,info="error",None
                errors.append(f"{movie_id} ({e})")
            if result=="stopped":
                continue
            count[result]+=1
            if info is not None:
                rows[movie_id]=info
            if result in ("ok","review"):
                removed.add(movie_id)
            elif result=="missing" and not os.path.exists(posterPath(movie_id)):
                added.add(movie_id)         # còn file poster (chưa cất đi được) thì không ghi là không có poster
            if k%100==0 or k==len(todo):
                print(f"[{k}/{len(todo)}] {verb} {count['ok']+count['review']} (cần xem lại {count['review']}), "
                      f"không có poster {count['missing']}, lỗi {count['error']}")
    except KeyboardInterrupt:
        print("Đã dừng theo yêu cầu; chạy lại lệnh để làm tiếp.")
        status=130
    finally:
        executor.shutdown(wait=False,cancel_futures=True)     # bỏ các việc chưa bắt đầu, lưu danh sách rồi mới chờ các luồng đang chạy
        try:
            if added or (removed&not_found):
                saveNotFound(added,removed)
        finally:
            try:
                if rows:
                    saveMap(rows)
            finally:
                executor.shutdown(wait=True)
    print(f"Xong sau {time.time()-start:.0f} giây: {verb} {count['ok']+count['review']}, không có poster {count['missing']}, lỗi {count['error']}.")
    flagged=sum(1 for r in rows.values() if r["status"] in ("review","rejected"))
    if flagged:
        print(f"{flagged} phim cần xem lại (cột status = review / rejected trong {file_map}).")
    if errors:
        print("Các phim bị lỗi (chạy lại lệnh để thử lại):",", ".join(errors[:10])+(" ..." if len(errors)>10 else ""))
    return status


if __name__=="__main__":
    sys.exit(main())
