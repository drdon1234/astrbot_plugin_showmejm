import os
import re
import glob
import yaml
from PIL import Image
import img2pdf
from typing import Dict, List, Any

def download_and_get_pdf(options: Dict[str, Any], arg: str) -> List[str]:
    """下载并生成PDF"""
    import jmcomic
    
    # 下载漫画
    try:
        album, _ = jmcomic.download_album(arg, jmcomic.JmOption.from_file(options['option']))
        downloaded_file_name = album.album_id
    except Exception as e:
        print(f"下载错误: {e}")
        print("尝试处理已下载的图片...")
        downloaded_file_name = arg
    
    # 读取配置确定路径
    with open(options['option'], "r", encoding="utf8") as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
    
    path = os.path.abspath(data["dir_rule"]["base_dir"])
    os.makedirs(path, exist_ok=True)
    
    # 查找已下载目录并处理
    with os.scandir(path) as entries:
        for entry in entries:
            if entry.is_dir() and downloaded_file_name == entry.name:
                # 检查是否已存在PDF
                real_name = glob.escape(entry.name)
                pattern = f"{path}/{real_name}*.pdf"
                matches = glob.glob(pattern)
                
                if matches:
                    print(f"文件：《{entry.name}》 已存在，直接返回")
                    return matches
                else:
                    print(f"开始转换：{entry.name}")
                    try:
                        return generate_pdf(options, os.path.join(path, entry.name), path, entry.name)
                    except Exception as e:
                        print(f"转换PDF错误: {e}")
                        raise e
    
    return []

def generate_pdf(options: Dict[str, Any], input_folder: str, pdf_path: str, pdf_name: str) -> List[str]:
    """生成PDF文件"""
    # 收集所有图片路径并排序
    image_paths = []
    for root, dirs, files in os.walk(input_folder):
        for dir_name in sorted(dirs, key=lambda x: int(x) if x.isdigit() else float('inf')):
            dir_path = os.path.join(root, dir_name)
            for file in sorted(os.listdir(dir_path),
                            key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else float('inf')):
                image_paths.append(os.path.join(dir_path, file))
    
    # 验证图片可用性
    valid_images = []
    for img_path in image_paths:
        try:
            with Image.open(img_path) as img:
                _ = img.size  # 测试图片是否可用
                valid_images.append(img_path)
        except Exception as e:
            print(f"跳过损坏图片: {img_path}, 错误: {e}")
    
    if not valid_images:
        raise Exception("没有有效的图片可以生成PDF")
    
    # 分批生成PDF
    pdf_files = []
    max_pages = options.get('pdf_max_pages', 200)
    chunks = [valid_images[i:i + max_pages] for i in range(0, len(valid_images), max_pages)]
    
    for idx, chunk in enumerate(chunks, 1):
        if len(chunks) > 1:
            final_pdf = os.path.abspath(os.path.join(pdf_path, f"{pdf_name} part {idx}.pdf"))
        else:
            final_pdf = os.path.abspath(os.path.join(pdf_path, f"{pdf_name}.pdf"))
        
        try:
            # 使用img2pdf直接生成PDF
            with open(final_pdf, "wb") as f:
                f.write(img2pdf.convert(chunk))
            
            pdf_files.append(final_pdf)
            print(f"成功生成PDF: {final_pdf}")
        except Exception as e:
            print(f"生成PDF错误: {e}")
    
    print(f"成功创建了 {len(pdf_files)} 个PDF文件")
    return pdf_files
