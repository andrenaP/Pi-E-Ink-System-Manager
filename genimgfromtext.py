from PIL import Image, ImageDraw, ImageFont

def paginate_text(text, font, display_size, margin=10, line_spacing=4):
    width, height = display_size
    max_text_width = width - 2 * margin
    max_text_height = height - 2 * margin

    words = text.split()
    lines = []
    line = ""
    draw_dummy = ImageDraw.Draw(Image.new("1", (1, 1)))

    for word in words:
        test_line = line + ("" if line == "" else " ") + word
        bbox = draw_dummy.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_text_width:
            line = test_line
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)

    pages = []
    y = margin
    page_lines = []
    bbox = draw_dummy.textbbox((0, 0), "A", font=font)
    line_height = (bbox[3] - bbox[1]) + line_spacing

    for line in lines:
        if y + line_height > height - margin:
            img = Image.new("1", (width, height), 255)
            draw = ImageDraw.Draw(img)
            y_draw = margin
            for l in page_lines:
                draw.text((margin, y_draw), l, font=font, fill=0)
                y_draw += line_height
            pages.append(img)
            page_lines = []
            y = margin
        page_lines.append(line)
        y += line_height

    if page_lines:
        img = Image.new("1", (width, height), 255)
        draw = ImageDraw.Draw(img)
        y_draw = margin
        for l in page_lines:
            draw.text((margin, y_draw), l, font=font, fill=0)
            y_draw += line_height
        pages.append(img)

    return pages



# ===== Пример использования =====
if __name__ == "__main__":
    WIDTH, HEIGHT = 400, 300
    font = ImageFont.truetype("Roboto-Regular.ttf", 20)

    #font = ImageFont.truetype("/data/data/com.termux/files/home/.termux/font.ttf", 20)

    text = (
        "Это очень длинный текст для проверки постраничного вывода. "
        "Функция автоматически разбивает его на строки по ширине дисплея "
        "и формирует несколько изображений, если текст не помещается на одной странице. "
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."

        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
        "Таким образом, можно показывать статьи, книги или новости на экране E-Ink."
    )

    pages = paginate_text(text, font, (WIDTH, HEIGHT))

    # Сохраним страницы для проверки
    for i, page in enumerate(pages):
        page.save(f"page_{i+1}.bmp")

