from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from .utils.config_manager import load_config
from .utils.domain_checker import get_usable_domain, update_option_domain, clear_domain
from .utils.jm_file_resolver import download_and_get_pdf
from .utils.message_adapter import MessageAdapter
from pathlib import Path
from jmcomic import JmOption
import os
import re
import asyncio
import random
import logging
import json
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


@register("astrbot_plugin_jmcomic", "test-do_not_download", "适配 AstrBot 的 JMComic 漫画搜索下载器", "1.0")
class JMComicBot(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = load_config(str(Path(__file__).parent / "config.yaml"))
        self.uploader = MessageAdapter(self.config)
        self._max_page_cache = {}

    @staticmethod
    def parse_command(message: str) -> List[str]:
        return [p for p in message.split(' ') if p][1:]

    @filter.command("搜jm")
    async def search_comic(self, event: AstrMessageEvent, cleaned_text: str):
        try:
            cleaned_text = re.sub(r'@\S+\s*', '', event.message_str).strip()
            args = self.parse_command(cleaned_text)

            if not args:
                await self.jm_helper(event)
                return

            query = args[0]
            page = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1

            await event.send(event.plain_result(f"正在搜索关键词: {query}，页码: {page}"))

            from jmcomic import JmOption
            option = JmOption.from_file(self.config['option_file'])
            client = option.new_jm_client(impl='api')

            tags = re.sub(r'[，,]+', ' ', query)
            search_page = client.search_site(search_query=tags, page=page)
            results = list(search_page.iter_id_title())

            if not results:
                await event.send(event.plain_result("未找到相关结果"))
                return

            cache_data = {}
            for idx, (album_id, title) in enumerate(results, 1):
                cache_data[str(idx)] = album_id

            search_cache_folder = Path(self.config['search_cache_folder'])
            search_cache_folder.mkdir(exist_ok=True, parents=True)

            cache_file = search_cache_folder / f"{event.get_sender_id()}.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            output = f"搜索结果 (第{page}页):\n"
            output += "=" * 50 + "\n"

            for i, (album_id, title) in enumerate(results, 1):
                output += f"[{i}] [{album_id}]: {title}\n"

            output += "\n输入 '下载漫画 序号' 或 '下载漫画 ID' 下载对应漫画"

            await event.send(event.plain_result(output))

        except Exception as e:
            logger.exception("搜索漫画失败")
            await event.send(event.plain_result(f"搜索漫画失败：{str(e)}"))

    @filter.command("随机jm")
    async def random_comic(self, event: AstrMessageEvent, cleaned_text: str):
        try:
            cleaned_text = re.sub(r'@\S+\s*', '', event.message_str).strip()
            args = self.parse_command(cleaned_text)

            tags = args[0] if args else ''

            await event.send(event.plain_result(f"正在随机寻找漫画{' (关键词: ' + tags + ')' if tags else ''}..."))

            option = JmOption.from_file(self.config['option_file'])
            client = option.new_jm_client(impl='api')

            # 获取最大页数
            max_page = await self.get_max_page(client, query=tags)

            if max_page == 0:
                await event.send(event.plain_result("未搜索到相关本子，请更换关键词"))
                return

            random_page = random.randint(1, max_page)
            result = client.search_site(search_query=tags, page=random_page)
            album_list = list(result.iter_id_title())

            if not album_list:
                await event.send(event.plain_result("未找到任何漫画"))
                return

            random_index = random.randint(0, len(album_list) - 1)
            selected_id = album_list[random_index][0]
            selected_title = album_list[random_index][1]

            result_text = f"你今天的幸运本子是：[{selected_id}]{selected_title}"
            await event.send(event.plain_result(result_text))

            choice = await event.ask_response("是否下载这个本子？(y/n):", timeout=30)
            if choice and choice.lower() == 'y':
                await self.download_comic_by_id(event, selected_id)

        except Exception as e:
            logger.exception("随机漫画失败")
            await event.send(event.plain_result(f"随机漫画失败：{str(e)}"))

    @filter.command("看jm")
    async def download_comic(self, event: AstrMessageEvent, cleaned_text: str):
        try:
            cleaned_text = re.sub(r'@\S+\s*', '', event.message_str).strip()
            args = self.parse_command(cleaned_text)

            if not args:
                await self.jm_helper(event)
                return

            comic_id = args[0]

            # 检查是否是序号
            if comic_id.isdigit():
                search_cache_folder = Path(self.config['search_cache_folder'])
                cache_file = search_cache_folder / f"{event.get_sender_id()}.json"

                if cache_file.exists():
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)

                    if comic_id in cache_data:
                        comic_id = cache_data[comic_id]
                        await event.send(event.plain_result(f"正在获取漫画 ID: {comic_id}"))
                    else:
                        # 如果不在缓存中，直接当作ID使用
                        await event.send(event.plain_result(f"正在获取漫画 ID: {comic_id}"))
                else:
                    await event.send(event.plain_result(f"正在获取漫画 ID: {comic_id}"))

            await self.download_comic_by_id(event, comic_id)

        except Exception as e:
            logger.exception("下载漫画失败")
            await event.send(event.plain_result(f"下载漫画失败：{str(e)}"))

    async def download_comic_by_id(self, event: AstrMessageEvent, comic_id: str):
        """下载指定ID的漫画"""
        try:
            await event.send(event.plain_result(f"开始下载漫画 {comic_id}，请稍候..."))

            pdf_files = download_and_get_pdf({
                'option': self.config['option_file'],
                'pdf_max_pages': self.config.get('pdf_max_pages', 200),
                'batch_size': self.config.get('batch_size', 20)
            }, comic_id)

            if not pdf_files:
                await event.send(event.plain_result("下载失败，未生成PDF文件"))
                return

            # 获取漫画名称
            folder_path = os.path.dirname(pdf_files[0])
            base_name = os.path.basename(pdf_files[0])
            name = os.path.splitext(base_name)[0]

            # 上传文件
            await self.uploader.upload_file(
                event,
                folder_path,
                name.split(' part')[0] if ' part' in name else name
            )

        except Exception as e:
            logger.exception("下载处理失败")
            await event.send(event.plain_result(f"下载处理失败：{str(e)}"))

    @filter.command("更新jm域名")
    async def update_domain(self, event: AstrMessageEvent, cleaned_text: str):
        try:
            await event.send(event.plain_result("正在检查可用域名..."))

            domains = get_usable_domain(self.config['option_file'])
            usable_domains = [domain for domain, status in domains if status == 'ok']

            if not usable_domains:
                await event.send(event.plain_result("未找到可用域名，请检查网络连接"))
                return

            update_option_domain(self.config['option_file'], usable_domains)
            await event.send(event.plain_result(f"已添加可用域名: {', '.join(usable_domains)}"))

        except Exception as e:
            logger.exception("更新域名失败")
            await event.send(event.plain_result(f"更新域名失败：{str(e)}"))

    @filter.command("清空jm域名")
    async def clear_domain_cmd(self, event: AstrMessageEvent, cleaned_text: str):
        try:
            clear_domain(self.config['option_file'])
            await event.send(event.plain_result("已清空域名配置"))

        except Exception as e:
            logger.exception("清空域名失败")
            await event.send(event.plain_result(f"清空域名失败：{str(e)}"))

    @filter.command("jm")
    async def jm_helper(self, event: AstrMessageEvent):
        help_text = """JMComic漫画下载器 指令帮助：
[1] 搜索漫画: 搜漫画 [关键词] [页码（默认1）]
[2] 随机推荐: 随机漫画 [关键词（可选）]
[3] 下载漫画: 下载漫画 [ID/序号]
[4] 更新域名: 更新域名
[5] 清空域名: 清空域名
[6] 重新加载配置: 重载漫画配置
[7] 获取指令帮助: 漫画

搜索多关键词时请用以下符号连接`,` `，`，关键词之间不要添加任何空格
使用"下载漫画 [序号]"前确保你最近至少使用过一次"搜漫画"命令（每个用户的缓存文件是独立的）"""
        await event.send(event.plain_result(help_text))

    @filter.command("重载jm配置")
    async def reload_config(self, event: AstrMessageEvent):
        await event.send(event.plain_result("正在重载配置参数"))
        self.config = load_config()
        self.uploader = MessageAdapter(self.config)
        await event.send(event.plain_result("已重载配置参数"))

    async def get_max_page(self, client, query=''):
        """获取最大页数"""
        if query in self._max_page_cache:
            return self._max_page_cache[query]

        try:
            result = client.search_site(search_query=query, page=1)
            if not result:  # 至少有一个相关本子才能通过下方逻辑寻找总页数，否则直接返回 0
                return 0

            current_page = 2000 if query == '' else 10  # 2025/4/20 - 根据开发经验硬编码的起始页数，理论上能减少迭代次数
            current_last_id = list(result.iter_id_title())[-1][0]

            # 模糊查找总页数边界，防止真实页数大于 current_page，每次扩展在当前基础上乘 2
            for _ in range(10):  # 假设 page <= 10 * 2^10 = 10240
                try:
                    current_result = client.search_site(search_query=query, page=current_page)
                    current_next_result = client.search_site(search_query=query, page=current_page + 1)
                    current_last_id = list(current_result.iter_id_title())[-1][0]
                    current_next_last_id = list(current_next_result.iter_id_title())[-1][0]
                    if current_last_id == current_next_last_id:
                        break
                    current_page *= 2
                except Exception:
                    return 0

            # 精确查找总页数，修改版二分迭代法
            low, high = 1, current_page
            while low + 1 < high:
                mid = (low + high) // 2
                try:
                    mid_result = client.search_site(search_query=query, page=mid)
                    mid_last_id = list(mid_result.iter_id_title())[-1][0]
                    if mid_last_id != current_last_id:
                        low = mid
                    else:
                        high = mid
                except Exception:
                    high = mid

            self._max_page_cache[query] = low
            return low

        except Exception as e:
            logger.error(f"获取最大页数错误: {e}")
            return 0

    async def terminate(self):
        """插件终止时的清理工作"""
        pass
