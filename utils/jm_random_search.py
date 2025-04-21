'''
随机漫画功能
贡献者 @drdon1234
'''
import os
import aiofiles
import json
from datetime import datetime, timedelta


class JmRandomSearch:
    # 是否正在查找最大页数
    is_max_page_finding = False

    def __init__(self, client):
        self.client = client
        self.cache_dir = os.path.join(os.path.dirname(__file__), "cache")
        self.cache_file = os.path.join(self.cache_dir, "jm_max_page.json")

    async def get_max_page(self, query='', initial_page=6000):
        print(f"正在获取搜索结果为 '{query}' 的分页目录总页数")
        self.is_max_page_finding = True
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            cache_data = {}
            if os.path.exists(self.cache_file):
                try:
                    async with aiofiles.open(self.cache_file, "r", encoding="utf-8") as f:
                        content = await f.read()
                        if content.strip():
                            cache_data = json.loads(content)
                except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
                    print(f"读取缓存文件时出错: {e}")
            if query in cache_data:
                cached_entry = cache_data[query]
                last_timestamp_str = cached_entry.get("timestamp")
                last_timestamp_dt = datetime.fromisoformat(last_timestamp_str) if last_timestamp_str else None
                if last_timestamp_dt and (datetime.now() - last_timestamp_dt <= timedelta(hours=24)):
                    print(f"查询 '{query}' 的缓存有效，最大页数为: {cached_entry['max_page']}")
                    return cached_entry["max_page"]
                print(f"查询 '{query}' 的缓存已过期，重新获取最大页数...")
            result = self.client.search_site(search_query=query, page=1)
            if not result:
                print("未搜索到相关本子，请尝试用其他语言的该关键词组搜索")
                return 0
            last_album_id = list(result.iter_id_title())[-1][0]
            print(f"第 1 页最后一个本子的 ID 为：{last_album_id}")
            low, high = 1, initial_page
            while low < high:
                mid = (low + high) // 2
                result = self.client.search_site(search_query=query, page=mid)
                if not result:
                    high = mid
                    continue
                current_last_album_id = list(result.iter_id_title())[-1][0]
                print(f"第 {mid} 页最后一个本子的 ID 为：{current_last_album_id}")
                if current_last_album_id == last_album_id:
                    high = mid
                else:
                    low = mid + 1
            max_page = low
            print(f"关键词 '{query}' 的分页目录总页数为 {max_page}")
            cache_data[query] = {
                "max_page": max_page,
                "timestamp": datetime.now().isoformat(),
                "reliable": True
            }
            try:
                async with aiofiles.open(self.cache_file, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(cache_data, ensure_ascii=False, indent=4))
                print(f"最大页码已保存到 {self.cache_file}，查询 '{query}' 的值为: {max_page}")
            except Exception as e:
                print(f"保存缓存文件时发生错误: {e}")
            return max_page
        finally:
            self.is_max_page_finding = False
