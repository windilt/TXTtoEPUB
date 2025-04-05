import os
import re
import shutil
import logging
from ebooklib import epub
from typing import NoReturn, List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constants ---
DEFAULT_VOLUME_TITLE = '默认卷'
DEFAULT_CHAPTER_TITLE = '开篇' # Changed from '默认章节' for better context
DEFAULT_AUTHOR = 'Unknown Author'
HTML_OUTPUT_FOLDER = './html_chapters'
CSS_STYLE_CONTENT = """
body {
    font-family: sans-serif;
}
p {
    text-indent: 2em; /* Add indentation to paragraphs */
    margin-top: 0;
    margin-bottom: 0;
    line-height: 1.6; /* Adjust line spacing */
}
h1 {
    text-align: center;
    font-weight: bold;
    margin-top: 1.5em;
    margin-bottom: 1em;
}
"""
CSS_FILE_NAME = "style/main.css" # Relative path within EPUB

import logging
from typing import List, Dict, Any

# --- Constants ---
DEFAULT_VOLUME_TITLE = '默认卷'
DEFAULT_CHAPTER_TITLE = '开篇'

class MultiLevelBook:
    """
    MultiLevelBook 用于存储和管理一个多级目录的书籍结构，包括卷和章节。
    Refactored to avoid recursion errors.
    """
    def __init__(self) -> None:
        """
        初始化 MultiLevelBook 实例，创建包含默认卷和默认章节的初始结构。
        """
        self.volumes: List[Dict[str, Any]] = []
        # Start with a default volume and chapter structure immediately
        self._create_default_structure()
        logging.debug("MultiLevelBook initialized with default structure.")

    def _create_default_structure(self):
        """Creates the initial default volume and chapter."""
        if not self.volumes: # Only if completely empty
            default_chapter = {'title': DEFAULT_CHAPTER_TITLE, 'content': []}
            default_volume = {'title': DEFAULT_VOLUME_TITLE, 'chapters': [default_chapter]}
            self.volumes.append(default_volume)

    def _is_initial_default_volume_empty(self) -> bool:
        """Checks if the book is still in its initial empty default state."""
        return (len(self.volumes) == 1 and
                self.volumes[0]['title'] == DEFAULT_VOLUME_TITLE and
                len(self.volumes[0]['chapters']) == 1 and
                self.volumes[0]['chapters'][0]['title'] == DEFAULT_CHAPTER_TITLE and
                not self.volumes[0]['chapters'][0]['content'])

    def _is_last_volume_chapterless(self) -> bool:
        """Checks if the last volume currently has no chapters."""
        return self.volumes and not self.volumes[-1]['chapters']

    def _is_last_chapter_default_and_empty(self) -> bool:
        """Checks if the last chapter in the last volume is the default one and empty."""
        if self.volumes and self.volumes[-1]['chapters']:
            last_chapter = self.volumes[-1]['chapters'][-1]
            return (last_chapter['title'] == DEFAULT_CHAPTER_TITLE and
                    not last_chapter['content'])
        return False

    def add_volume(self, title: str) -> None:
        """
        添加一个新卷到书籍中。
        如果当前只有一个空的默认卷，则重命名该卷。否则，添加新卷。
        :param title: 新卷的标题，类型为字符串。
        """
        if self._is_initial_default_volume_empty():
            self.volumes[0]['title'] = title
            logging.info(f"Renamed initial default volume to: {title}")
        else:
            # Ensure the previous volume wasn't left chapterless unnecessarily
            if self._is_last_volume_chapterless():
                 logging.warning(f"Adding new volume '{title}', but previous volume '{self.volumes[-1]['title']}' had no chapters.")
                 # Optionally add a default chapter to the previous one here if desired?
                 # self.add_chapter_to_volume(len(self.volumes) - 1, DEFAULT_CHAPTER_TITLE)

            self.volumes.append({'title': title, 'chapters': []}) # New volumes start with no chapters
            logging.info(f"Added volume: {title}")

    def add_chapter_to_last_volume(self, title: str, content: List[str] = None) -> None:
        """
        在最后一个卷中添加一个新章节。
        如果最后一个卷没有章节，或者最后一个章节是空的默认章节，则替换/设置它。否则，追加新章节。
        :param title: 新章节的标题，类型为字符串。
        :param content: 新章节的内容列表，类型为字符串列表，如果没有提供，默认为空列表。
        """
        if content is None:
            content = []

        if not self.volumes:
            # This case should not happen due to __init__, but as a safeguard:
            self._create_default_structure()
            logging.warning("Attempted to add chapter when no volumes existed. Created default structure.")

        last_volume = self.volumes[-1]

        # If the last volume has no chapters OR if its last chapter is the empty default one
        if not last_volume['chapters'] or self._is_last_chapter_default_and_empty():
             if last_volume['chapters']: # Replace the empty default chapter
                 last_volume['chapters'][-1]['title'] = title
                 last_volume['chapters'][-1]['content'] = content
                 logging.info(f"Replaced default chapter in volume '{last_volume['title']}' with: {title}")
             else: # Add as the first chapter
                 last_volume['chapters'].append({'title': title, 'content': content})
                 logging.info(f"Added first chapter '{title}' to volume '{last_volume['title']}'")
        else: # Append as a new chapter
            last_volume['chapters'].append({'title': title, 'content': content})
            logging.info(f"Appended chapter '{title}' to volume '{last_volume['title']}'")

    def add_content_to_last_chapter(self, line: str) -> None:
        """
        向最后一个卷的最后一个章节添加内容行。
        如果最后一个卷没有章节，会自动添加一个默认章节。
        :param line: 要添加到最后一个章节的内容行，类型为字符串。
        """
        if not self.volumes:
            # Safeguard, should be handled by __init__
            self._create_default_structure()
            logging.warning("Attempted to add content when no volumes existed. Created default structure.")

        # Ensure the last volume has at least one chapter before adding content
        if self._is_last_volume_chapterless():
            logging.warning(f"Volume '{self.volumes[-1]['title']}' had no chapters when adding content. Adding default chapter '{DEFAULT_CHAPTER_TITLE}'.")
            self.add_chapter_to_last_volume(DEFAULT_CHAPTER_TITLE) # Add a default chapter

        # Now we are sure the last volume has at least one chapter
        try:
            self.volumes[-1]['chapters'][-1]['content'].append(line)
            # logging.debug(f"Added content line to {self.volumes[-1]['title']} / {self.volumes[-1]['chapters'][-1]['title']}")
        except IndexError:
             # This catch might be redundant now but kept as extra safety
             logging.error("Critical error: Could not find chapter to add content to, even after checks.")
             # Fallback: try creating default structure again? Or raise error?
             self._create_default_structure()
             if self.volumes and self.volumes[-1]['chapters']:
                  self.volumes[-1]['chapters'][-1]['content'].append(line)



class TextBookParser:
    """
    解析TXT文本文件，生成MultiLevelBook结构，使用正则表达式匹配卷和章节。
    """
    # Regex to match potential chapter/volume titles
    # Allows for spaces/tabs/full-width spaces at the start
    # Matches patterns like "第x卷", "第y章", "卷z", "章k", "第一回", etc.
    TITLE_PATTERN = r"^[\s\u3000]*([第卷][0-9一二三四五六七八九十零〇百千两]+[卷])?[\s\u3000]*([第章节回部节集篇辑][0-9一二三四五六七八九十零〇百千两]+[章节回部节集篇辑])?[\s\u3000]*(.*)"
    # Simpler pattern focusing on common structures, might need adjustment for complex cases
    TITLE_PATTERN_SIMPLE = r"^[\s\u3000]*[第卷][0-9一二三四五六七八九十零〇百千两]+[章回部节集卷篇辑][\s\u3000]*.*"


    @staticmethod
    def read(file_path: str) -> Optional[MultiLevelBook]:
        """
        读取文本文件并解析成一个多级书籍结构。
        :param file_path: TXT文件的路径。
        :return: MultiLevelBook对象，包含解析后的卷和章节信息，或在文件无法读取时返回 None。
        """
        multi_level_book = MultiLevelBook() # Initializes with default volume/chapter

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if not line: # Skip empty lines
                        continue

                    # Check if the line matches the title pattern
                    match = re.match(TextBookParser.TITLE_PATTERN_SIMPLE, line)
                    if match:
                        title_text = line # Use the full line as title for simplicity

                        # Heuristic to differentiate volumes from chapters
                        # This might need refinement based on actual book formats
                        if "卷" in title_text and ("章" not in title_text and "回" not in title_text and "节" not in title_text):
                            logging.info(f"Detected Volume Title: {title_text}")
                            # Check if the last chapter of the previous volume was empty, if so, remove it
                            if multi_level_book.volumes and multi_level_book.volumes[-1]['chapters'] and not multi_level_book.volumes[-1]['chapters'][-1]['content']:
                                removed_chapter = multi_level_book.volumes[-1]['chapters'].pop()
                                logging.info(f"Removed empty chapter '{removed_chapter['title']}' before adding new volume.")
                            multi_level_book.add_volume(title_text)
                            # After adding a new volume, we expect a chapter next,
                            # so we don't add a default chapter here immediately.
                        else: # Assume it's a chapter title
                            logging.info(f"Detected Chapter Title: {title_text}")
                            multi_level_book.add_chapter_to_last_volume(title_text)

                    else: # It's content
                        multi_level_book.add_content_to_last_chapter(line)

            # Final check: remove trailing empty default chapter/volume if they exist
            if multi_level_book.volumes:
                last_volume = multi_level_book.volumes[-1]
                if last_volume['chapters']:
                    last_chapter = last_volume['chapters'][-1]
                    if not last_chapter['content'] and last_chapter['title'] in [DEFAULT_CHAPTER_TITLE, DEFAULT_VOLUME_TITLE]: # Check if it's an empty default
                         last_volume['chapters'].pop()
                         logging.info(f"Removed trailing empty default chapter '{last_chapter['title']}'.")
                # If removing the chapter made the volume empty, and it's a default volume, remove it too
                if not last_volume['chapters'] and last_volume['title'] == DEFAULT_VOLUME_TITLE and len(multi_level_book.volumes) > 1:
                    multi_level_book.volumes.pop()
                    logging.info("Removed trailing empty default volume.")


            return multi_level_book

        except FileNotFoundError:
            logging.error(f"Error: TXT file not found at {file_path}")
            return None
        except Exception as e:
            logging.error(f"Error reading or parsing TXT file {file_path}: {e}")
            return None

    @staticmethod
    def save_chapters_as_html(multi_level_book: MultiLevelBook, output_folder: str) -> bool:
        """
        将书籍的每个章节保存为HTML文件，使用编号来命名文件。
        Includes basic CSS linking.
        :param multi_level_book: 包含卷和章节信息的MultiLevelBook对象。
        :param output_folder: HTML文件保存的目录。
        :return: True if successful, False otherwise.
        """
        if not multi_level_book or not multi_level_book.volumes:
            logging.warning("No volumes found in the book structure to save.")
            return False

        os.makedirs(output_folder, exist_ok=True)
        success = True

        for volume_index, volume in enumerate(multi_level_book.volumes, start=1):
            for chapter_index, chapter in enumerate(volume['chapters'], start=1):
                # Use numbering for filenames: "vol_chap.html" (e.g., "001_001.html")
                file_name = f"{volume_index:03}_{chapter_index:03}.html"
                file_path = os.path.join(output_folder, file_name)
                logging.debug(f"Generating HTML file: {file_path}")

                try:
                    with open(file_path, 'w', encoding='utf-8') as chapter_file:
                        chapter_file.write('<!DOCTYPE html>\n')
                        chapter_file.write('<html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN">\n<head>\n')
                        chapter_file.write(f'  <meta charset="utf-8"/>\n')
                        chapter_file.write(f'  <title>{chapter["title"]}</title>\n')
                        # Link the CSS file relative to the EPUB root
                        chapter_file.write(f'  <link rel="stylesheet" type="text/css" href="{CSS_FILE_NAME}"/>\n')
                        chapter_file.write('</head>\n<body>\n')
                        chapter_file.write(f'  <h1>{chapter["title"]}</h1>\n')
                        # Write each line of content as a separate paragraph
                        for line in chapter['content']:
                            # Basic HTML escaping for safety, though full escaping might be needed
                            escaped_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                            chapter_file.write(f'  <p>{escaped_line}</p>\n')
                        chapter_file.write('</body>\n</html>')
                except IOError as e:
                    logging.error(f"Failed to write HTML file {file_path}: {e}")
                    success = False
                except Exception as e:
                     logging.error(f"An unexpected error occurred while writing {file_path}: {e}")
                     success = False

        return success

class TxtToEpubConverter:
    def __init__(self, txt_path: str, epub_path: str, book_title: str, author_name: str,
                 cover_image: Optional[str] = None,
                 output_folder: str = HTML_OUTPUT_FOLDER,
                 progress_callback=None):
        """
        初始化转换器实例。
        :param txt_path: TXT文件的路径。
        :param epub_path: 输出的EPUB文件路径。
        :param book_title: 电子书标题。
        :param author_name: 作者名。
        :param cover_image: 封面图片文件的路径 (可选)。
        :param output_folder: 存放临时HTML章节文件的目录。
        :param progress_callback: 回调函数，用于报告进度 (0-100)。
        """
        self.txt_path = txt_path
        self.epub_path = epub_path
        self.book_title = book_title
        self.author_name = author_name or DEFAULT_AUTHOR
        self.cover_image_path = cover_image
        self.output_folder = output_folder
        self.progress_callback = progress_callback
        self.generated_cover_path: Optional[str] = None

    def _update_progress(self, value: int):
        """Safely calls the progress callback."""
        if self.progress_callback:
            try:
                self.progress_callback(min(max(value, 0), 100)) # Clamp value between 0-100
            except Exception as e:
                logging.warning(f"Progress callback failed: {e}")

    def generate_cover(self) -> Optional[str]:
        """
        Generates a simple cover image if no cover is provided.
        :return: Path to the generated cover image, or None if failed.
        """
        width, height = 600, 800
        background_color = (240, 240, 240) # Light grey background
        font_color = (50, 50, 50) # Dark grey text
        cover_path = os.path.join(self.output_folder, 'cover.jpg')

        try:
            image = Image.new('RGB', (width, height), background_color)
            draw = ImageDraw.Draw(image)

            # Attempt to load a default font (consider allowing custom fonts)
            try:
                # Use a slightly larger default font size if possible
                font_size = 40
                font = ImageFont.truetype("arial.ttf", font_size) # Try common Arial
            except IOError:
                 try:
                     font_size = 30 # Try again with default load (might be small)
                     font = ImageFont.load_default()
                     logging.warning("Arial font not found, using default PIL font for cover.")
                 except Exception as font_e:
                     logging.error(f"Could not load any font for cover generation: {font_e}")
                     return None

            # Calculate text position for centering
            # Use textbbox for more accurate centering with different fonts/sizes
            text_bbox = draw.textbbox((0, 0), self.book_title, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = (width - text_width) / 2
            text_y = (height - text_height) / 2

            draw.text((text_x, text_y), self.book_title, fill=font_color, font=font)

            image.save(cover_path, "JPEG") # Specify format
            logging.info(f"Generated default cover image at: {cover_path}")
            self.generated_cover_path = cover_path # Store path for cleanup
            return cover_path
        except ImportError:
             logging.error("PIL (Pillow) is required for cover generation but seems unavailable.")
             return None
        except Exception as e:
            logging.error(f"Failed to generate cover image: {e}")
            return None

    def convert(self):
        """
        执行 TXT 到 EPUB 的转换过程。
        """
        logging.info(f"Starting conversion for '{self.book_title}'...")
        self._update_progress(0)

        # 1. Create output directory
        try:
            os.makedirs(self.output_folder, exist_ok=True)
        except OSError as e:
             logging.error(f"Failed to create output directory {self.output_folder}: {e}")
             return # Cannot proceed without output folder

        # 2. Parse the TXT file
        logging.info("Parsing TXT file...")
        parser = TextBookParser()
        book_structure = parser.read(self.txt_path)
        if book_structure is None:
            logging.error("Failed to parse TXT file. Aborting conversion.")
            self.cleanup()
            return
        self._update_progress(15) # Progress after parsing

        # 3. Save chapters as HTML files
        logging.info("Saving chapters as HTML files...")
        if not parser.save_chapters_as_html(book_structure, self.output_folder):
             logging.error("Failed to save chapters as HTML. Aborting conversion.")
             self.cleanup()
             return
        self._update_progress(40) # Progress after HTML generation

        # 4. Create EPUB book and set metadata
        book = epub.EpubBook()
        book.set_identifier(f"urn:uuid:{os.path.basename(self.txt_path)}-{hash(self.book_title)}") # Basic unique ID
        book.set_title(self.book_title)
        book.set_language('zh-cn')
        book.add_author(self.author_name)

        # 5. Add cover image
        final_cover_path = None
        if self.cover_image_path and os.path.isfile(self.cover_image_path):
            final_cover_path = self.cover_image_path
            logging.info(f"Using provided cover image: {final_cover_path}")
        else:
            if self.cover_image_path:
                 logging.warning(f"Provided cover image path not found: {self.cover_image_path}. Generating default cover.")
            final_cover_path = self.generate_cover()

        if final_cover_path and os.path.isfile(final_cover_path):
            try:
                cover_filename = os.path.basename(final_cover_path)
                with open(final_cover_path, 'rb') as cover_file:
                    book.set_cover(cover_filename, cover_file.read())
                # Add the cover image explicitly as an item if it wasn't generated by us
                # (ebooklib adds the generated one automatically when set_cover is used)
                # if final_cover_path != self.generated_cover_path:
                #    book.add_item(epub.EpubImage(uid='cover-image', file_name=cover_filename, media_type='image/jpeg', content=open(final_cover_path, 'rb').read()))

            except IOError as e:
                 logging.error(f"Failed to read cover image file {final_cover_path}: {e}")
            except Exception as e:
                 logging.error(f"Failed to set cover image: {e}")
        else:
             logging.warning("No valid cover image found or generated.")

        self._update_progress(50) # Progress after cover handling

        # 6. Prepare EPUB book structure (TOC, Spine, CSS)
        spine: List[Any] = ['nav'] # Start spine with nav
        toc: List[Any] = []

        # Create and add CSS item
        style_css = epub.EpubItem(uid="style_main", file_name=CSS_FILE_NAME,
                                  media_type="text/css", content=CSS_STYLE_CONTENT.encode('utf-8'))
        book.add_item(style_css)

        total_chapters = sum(len(volume.get('chapters', [])) for volume in book_structure.volumes)
        chapters_processed = 0
        logging.info("Adding chapters to EPUB...")

        # 7. Iterate through book structure and add items to EPUB
        for volume_index, volume in enumerate(book_structure.volumes, start=1):
            volume_title = volume.get('title', f'Volume {volume_index}')
            volume_chapters = volume.get('chapters', [])

            # Create a list for chapter links within this volume section in TOC
            toc_volume_chapters = []

            for chapter_index, chapter in enumerate(volume_chapters, start=1):
                chapter_title = chapter.get('title', f'Chapter {chapter_index}')
                html_file_name = f"{volume_index:03}_{chapter_index:03}.html"
                html_file_path = os.path.join(self.output_folder, html_file_name)

                try:
                    with open(html_file_path, 'r', encoding="utf-8") as f:
                        html_content = f.read()

                    # Create EpubHtml item for the chapter
                    chapter_item = epub.EpubHtml(title=chapter_title,
                                                 file_name=html_file_name,
                                                 lang='zh-cn',
                                                 content=html_content.encode('utf-8')) # Content needs to be bytes

                    # Link the CSS file to this chapter
                    chapter_item.add_item(style_css) # ebooklib < 0.18
                    # chapter_item.add_link(href=CSS_FILE_NAME, rel='stylesheet', type='text/css') # ebooklib >= 0.18


                    book.add_item(chapter_item)
                    spine.append(chapter_item) # Add chapter to reading order
                    # Add chapter link to the current volume's list for TOC
                    toc_volume_chapters.append(epub.Link(html_file_name, chapter_title, f"vol{volume_index}-chap{chapter_index}"))

                    chapters_processed += 1
                    # Dynamic progress update
                    progress = 50 + int((chapters_processed / total_chapters) * 45) # Chapters take up 45%
                    self._update_progress(progress)

                except FileNotFoundError:
                    logging.error(f"HTML chapter file not found: {html_file_path}. Skipping chapter.")
                except IOError as e:
                    logging.error(f"Failed to read HTML chapter file {html_file_path}: {e}. Skipping chapter.")
                except Exception as e:
                    logging.error(f"Error processing chapter '{chapter_title}': {e}. Skipping chapter.")


            # Add the volume section to the main TOC only if it has chapters
            if toc_volume_chapters:
                 # Use the first chapter item as the href for the section title, or create a dummy page?
                 # Using the first chapter's link is common practice.
                 # toc.append(epub.Section(volume_title, href=toc_volume_chapters[0].href)) # Section Title
                 # toc.extend(toc_volume_chapters) # Add chapter links under the section

                 # Alternative: Nested TOC structure
                 toc.append((epub.Section(volume_title), tuple(toc_volume_chapters)))


        # 8. Set EPUB spine and TOC
        book.spine = spine
        book.toc = tuple(toc) # Convert list of tuples/links to tuple

        # 9. Add standard EPUB items (NCX, Nav)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # 10. Write EPUB file
        logging.info(f"Writing EPUB file to: {self.epub_path}")
        try:
            epub.write_epub(self.epub_path, book, {})
            self._update_progress(98) # Progress before cleanup
            logging.info("EPUB file created successfully.")
        except Exception as e:
            logging.error(f"Failed to write EPUB file {self.epub_path}: {e}")
            # Don't cleanup if EPUB writing failed, user might want intermediate files
            return # Stop here

        # 11. Cleanup temporary files
        self.cleanup()
        self._update_progress(100) # Final progress
        logging.info(f"Conversion complete for '{self.book_title}'.")


    def cleanup(self) -> NoReturn:
        """
        清理输出目录中的所有临时文件和生成的封面。
        """
        logging.info(f"Cleaning up temporary files in {self.output_folder}...")
        if os.path.isdir(self.output_folder):
            try:
                # Remove generated cover first if it exists inside the folder
                if self.generated_cover_path and os.path.dirname(self.generated_cover_path) == self.output_folder:
                    if os.path.isfile(self.generated_cover_path):
                        os.unlink(self.generated_cover_path)
                        logging.debug(f"Removed generated cover: {self.generated_cover_path}")

                # Remove the rest of the folder contents (HTML files)
                # Using rmtree is simpler if the whole folder is temporary
                shutil.rmtree(self.output_folder)
                logging.info(f"Removed temporary directory: {self.output_folder}")

            except OSError as e:
                logging.error(f"Error during cleanup of {self.output_folder}: {e}")
            except Exception as e:
                logging.error(f"Unexpected error during cleanup: {e}")
        else:
            logging.info("Temporary folder not found, skipping cleanup.")


def convert_all_txt_in_directory(directory_path: str):
    """
    遍历指定目录，自动处理其中的所有txt文件，转换为epub文件。
    :param directory_path: 目录路径
    """
    if not os.path.isdir(directory_path):
        logging.error(f"Provided path is not a valid directory: {directory_path}")
        return

    logging.info(f"Scanning directory for TXT files: {directory_path}")
    txt_files = [f for f in os.listdir(directory_path) if f.lower().endswith('.txt')]

    if not txt_files:
        logging.info("No TXT files found in the directory.")
        return

    logging.info(f"Found {len(txt_files)} TXT file(s) to convert.")

    for txt_file in txt_files:
        base_name = os.path.splitext(txt_file)[0]
        txt_path = os.path.join(directory_path, txt_file)
        epub_path = os.path.join(directory_path, f"{base_name}.epub")
        # Look for cover image with common extensions (jpg, jpeg, png)
        cover_image_path = None
        for ext in ['.jpg', '.jpeg', '.png']:
             potential_cover = os.path.join(directory_path, f"{base_name}{ext}")
             if os.path.isfile(potential_cover):
                 cover_image_path = potential_cover
                 logging.info(f"Found cover image for {txt_file}: {cover_image_path}")
                 break

        book_title = base_name # Use filename as title
        author_name = DEFAULT_AUTHOR # Default author

        logging.info(f"--- Processing file: {txt_file} ---")
        converter = TxtToEpubConverter(txt_path, epub_path, book_title, author_name, cover_image_path)

        try:
            converter.convert()
            logging.info(f"--- Finished processing: {txt_file} ---")
        except Exception as e:
            # Catch errors during conversion of a single file
            logging.error(f"!!! Failed to convert {txt_file}: {e} !!!")
            # Optionally cleanup if converter failed mid-way and left files
            converter.cleanup()
            logging.info(f"--- Aborted processing: {txt_file} ---")


if __name__ == '__main__':
    current_directory = os.getcwd()
    logging.info(f"Starting TXT to EPUB conversion in directory: {current_directory}")
    convert_all_txt_in_directory(current_directory)
    logging.info("Batch conversion process finished.")


#gemini-2.5-pro-exp-03-25:free 2025-4-5改进
