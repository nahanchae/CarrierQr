from pystrich.datamatrix import DataMatrixEncoder
from PIL import Image
import ezdxf
from ezdxf import units
from ezdxf.colors import rgb2int
import os
import tempfile


def make_datamatrix_image(data):
    """
    문자열 data를 DataMatrix 이미지로 생성
    """
    encoder = DataMatrixEncoder(data)

    temp_dir = tempfile.gettempdir()
    temp_file = os.path.join(temp_dir, f"temp_{data}.png")

    encoder.save(temp_file)

    img = Image.open(temp_file).convert("L")
    return img


def trim_white_margin(img):
    """
    DataMatrix 이미지 주변 흰색 여백 제거
    실제 코드 영역만 남김
    """
    width, height = img.size

    min_x = width
    min_y = height
    max_x = 0
    max_y = 0

    found_black = False

    for y in range(height):
        for x in range(width):
            pixel = img.getpixel((x, y))

            if pixel < 128:
                found_black = True

                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y

    if not found_black:
        return img

    return img.crop((min_x, min_y, max_x + 1, max_y + 1))


def add_solid_rect(entity_space, x1, y1, x2, y2, rgb):
    """
    사각형 영역을 HATCH로 채우는 함수
    """
    hatch = entity_space.add_hatch(dxfattribs={"solid_fill": 1})
    hatch.rgb = rgb

    hatch.paths.add_polyline_path(
        [
            (x1, y1),
            (x2, y1),
            (x2, y2),
            (x1, y2),
        ],
        is_closed=True
    )


def create_datamatrix_block(doc, data, code_size=12.0, add_outline=True):
    """
    DataMatrix 코드만 BLOCK으로 생성

    - 코드 배경: 흰색
    - 검정 셀: 검정색
    - 실제 코드 크기: 12 x 12 mm
    - 외곽선: 흰색, 꼭짓점 스냅용
    """

    block_name = data

    if block_name in doc.blocks:
        block_name = data + "_BLOCK"

    block = doc.blocks.new(name=block_name)

    img = make_datamatrix_image(data)
    img = trim_white_margin(img)

    width, height = img.size

    cell_size_x = code_size / width
    cell_size_y = code_size / height

    # 1. 코드 흰색 배경 12 x 12mm
    add_solid_rect(
        entity_space=block,
        x1=0,
        y1=0,
        x2=code_size,
        y2=code_size,
        rgb=(255, 255, 255)
    )

    # 2. 검정 코드 부분 채우기
    for y in range(height):
        x = 0

        while x < width:
            pixel = img.getpixel((x, y))

            if pixel < 128:
                start_x = x

                while x < width and img.getpixel((x, y)) < 128:
                    x += 1

                end_x = x

                cad_x1 = start_x * cell_size_x
                cad_x2 = end_x * cell_size_x

                # 이미지 y축은 아래 방향, CAD y축은 위 방향
                cad_y1 = (height - y - 1) * cell_size_y
                cad_y2 = (height - y) * cell_size_y

                add_solid_rect(
                    entity_space=block,
                    x1=cad_x1,
                    y1=cad_y1,
                    x2=cad_x2,
                    y2=cad_y2,
                    rgb=(0, 0, 0)
                )

            else:
                x += 1

    # 3. 흰색 외곽선, 꼭짓점 스냅용
    if add_outline:
        block.add_lwpolyline(
            [
                (0, 0),
                (code_size, 0),
                (code_size, code_size),
                (0, code_size),
                (0, 0),
            ],
            dxfattribs={
                "true_color": rgb2int((255, 255, 255))
            }
        )

    return block_name


def add_comment_text(msp, data, x, y):
    """
    텍스트를 DataMatrix 블록과 분리해서 일반 TEXT로 추가
    """

    text = msp.add_text(
        data,
        dxfattribs={
            "height": 2.0,
            "true_color": rgb2int((0, 0, 0))
        }
    )

    # 코드 아래쪽에 문자 배치
    text.set_placement((x, y - 3.0))


def add_frame(msp, x, y, frame_width=128.0, frame_height=180.0, fill_white=True):
    """
    128 x 180mm 프레임 생성

    x, y는 프레임 좌측 상단 기준
    """

    # 1. 프레임 내부 흰색 배경
    if fill_white:
        add_solid_rect(
            entity_space=msp,
            x1=x,
            y1=y - frame_height,
            x2=x + frame_width,
            y2=y,
            rgb=(255, 255, 255)
        )

    # 2. 프레임 외곽선
    msp.add_lwpolyline(
        [
            (x, y),
            (x + frame_width, y),
            (x + frame_width, y - frame_height),
            (x, y - frame_height),
            (x, y),
        ],
        dxfattribs={
            "true_color": rgb2int((0, 0, 0))
        }
    )


def make_datamatrix_dxf(
    output_file="datamatrix_28sets_12mm_down.dxf",
    code_size=12.0,

    frame_width=128.0,
    frame_height=180.0,

    sets_per_row=4,
    frame_gap_x=15.0,
    frame_gap_y=15.0,

    code_down_offset=12.0,   # 전체 코드 12mm 아래 이동

    add_label=True,
    add_outline=True,
    add_frame_line=True,
    fill_frame_white=True
):
    """
    0001 ~ 0028까지 총 28세트 생성

    프레임:
    - 크기: 128 x 180mm
    - 내부: 흰색 배경
    - 외곽: 검정선

    한 세트 배치:

    ASDC    BSDC    CSDC

    DSDC    ESDC    FSDC

    GSDC    HSDC    ISDC


            JSDC

    텍스트 표시는 ESDC, JSDC만 표시

    code_down_offset=12.0 으로 전체 DataMatrix 코드와 텍스트를
    기존 위치보다 12mm 아래로 이동
    """

    doc = ezdxf.new("R2010")
    doc.units = units.MM

    msp = doc.modelspace()

    total_sets = 28

    # QR.dxf 기준 코드 위치
    # 기준: 프레임 좌측 상단에서 떨어진 거리
    # x_offset: 왼쪽에서 오른쪽 거리
    # y_offset: 위에서 아래로 내려가는 거리
    code_positions = {
        "A": (40.0, 36.0),
        "B": (58.0, 36.0),
        "C": (76.0, 36.0),

        "D": (40.0, 54.0),
        "E": (58.0, 54.0),
        "F": (76.0, 54.0),

        "G": (40.0, 72.0),
        "H": (58.0, 72.0),
        "I": (76.0, 72.0),

        # JSDC는 가운데 아래
        "J": (58.0, 114.0),
    }

    # 텍스트를 표시할 코드만 지정
    label_prefixes = ["E", "J"]

    for set_num in range(1, total_sets + 1):
        number = f"{set_num:04d}"

        set_index = set_num - 1

        # 28세트를 여러 프레임으로 배치
        set_col = set_index % sets_per_row
        set_row = set_index // sets_per_row

        # 각 프레임 좌측 상단 좌표
        frame_x = set_col * (frame_width + frame_gap_x)
        frame_y = -set_row * (frame_height + frame_gap_y)

        # 128 x 180 흰색 배경 + 외곽선
        if add_frame_line:
            add_frame(
                msp=msp,
                x=frame_x,
                y=frame_y,
                frame_width=frame_width,
                frame_height=frame_height,
                fill_white=fill_frame_white
            )

        # 프레임 안에 A~J 배치
        for prefix, offset in code_positions.items():
            offset_x, offset_y = offset

            data = prefix + "SDC" + number

            # DataMatrix 좌측 하단 위치
            # 기존 위치보다 전체적으로 12mm 아래로 이동
            x = frame_x + offset_x
            y = frame_y - offset_y - code_down_offset

            # DataMatrix 블록 생성
            block_name = create_datamatrix_block(
                doc=doc,
                data=data,
                code_size=code_size,
                add_outline=add_outline
            )

            # DataMatrix 삽입
            msp.add_blockref(
                block_name,
                insert=(x, y)
            )

            # 텍스트는 ESDC, JSDC만 표시
            if add_label and prefix in label_prefixes:
                add_comment_text(
                    msp=msp,
                    data=data,
                    x=x,
                    y=y
                )

            print(data)

    doc.saveas(output_file)

    print()
    print("DXF 파일 생성 완료:", output_file)
    print("프레임 크기:", frame_width, "x", frame_height, "mm")
    print("프레임 배경:", "흰색" if fill_frame_white else "없음")
    print("DataMatrix 크기:", code_size, "x", code_size, "mm")
    print("코드 전체 이동:", code_down_offset, "mm 아래")
    print("총 세트:", total_sets, "세트")
    print("총 코드 개수:", total_sets * 10, "개")
    print("텍스트 표시:", "ESDC, JSDC만")
    print("한 줄 세트 개수:", sets_per_row)


# 실행
make_datamatrix_dxf(
    output_file="datamatrix_28sets_12mm_down.dxf",

    code_size=12.0,

    frame_width=128.0,
    frame_height=180.0,

    sets_per_row=4,       # 한 줄에 4세트 배치
    frame_gap_x=15.0,     # 프레임끼리 가로 간격
    frame_gap_y=15.0,     # 프레임끼리 세로 간격

    code_down_offset=12.0, # 전체 코드 12mm 아래 이동

    add_label=True,        # 텍스트 표시 기능 사용
    add_outline=True,      # 흰색 외곽선, 꼭짓점 스냅용
    add_frame_line=True,   # 128x180 외곽선 표시
    fill_frame_white=True  # 128x180 내부 흰색 배경
)