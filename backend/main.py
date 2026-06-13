import os
import base64
import math
import re

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://statkjh1-collab.github.io",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 수학 계산 엔진 ────────────────────────────────────────────────────────────

SAFE_FUNCTIONS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log10, "ln": math.log, "abs": abs,
    "pi": math.pi, "e": math.e, "pow": pow, "round": round,
}


def preprocess(expr: str) -> str:
    expr = expr.replace("×", "*").replace("÷", "/").replace("^", "**")
    superscripts = {"⁰":"0","¹":"1","²":"2","³":"3","⁴":"4","⁵":"5","⁶":"6","⁷":"7","⁸":"8","⁹":"9"}
    i, result = 0, []
    while i < len(expr):
        ch = expr[i]
        if ch in superscripts:
            exp_digits = []
            while i < len(expr) and expr[i] in superscripts:
                exp_digits.append(superscripts[expr[i]])
                i += 1
            result.append("**" + "".join(exp_digits))
        else:
            result.append(ch)
            i += 1
    expr = "".join(result)
    expr = re.sub(r"(\d)(sqrt|sin|cos|tan|log|ln|abs)", r"\1*\2", expr)
    return expr


def solve_linear(left: str, right_val: float) -> str:
    left = left.replace(" ", "").lower()
    pattern = re.fullmatch(r"([+-]?\d*\.?\d*)x([+-]\d+\.?\d*)?", left)
    if not pattern:
        return "일차방정식 형태(예: 2x + 4 = 10)만 지원해요."
    a_str = pattern.group(1)
    b_str = pattern.group(2) or "0"
    a = float(a_str) if a_str not in ("", "+", "-") else float(a_str + "1")
    b = float(b_str)
    if a == 0:
        return "x의 계수가 0이라 풀 수 없어요."
    x = (right_val - b) / a
    x_display = int(x) if x == int(x) else round(x, 4)
    steps = (
        f"  {left} = {right_val}\n"
        f"  {a}x = {right_val} - ({b}) = {right_val - b}\n"
        f"  x = {right_val - b} ÷ {a} = {x_display}"
    )
    return f"x = {x_display}\n\n풀이 과정:\n{steps}"


def solve_equation(problem: str) -> str:
    sides = problem.split("=")
    if len(sides) != 2:
        return "방정식 형식이 맞지 않아요. 예: 2x + 4 = 10"
    left, right = sides[0].strip(), sides[1].strip()
    try:
        right_val = float(eval(preprocess(right), {"__builtins__": {}}, SAFE_FUNCTIONS))
    except Exception:
        return "등호 오른쪽을 계산할 수 없어요."
    if "x" in left.lower():
        return solve_linear(left, right_val)
    try:
        left_val = float(eval(preprocess(left), {"__builtins__": {}}, SAFE_FUNCTIONS))
        return f"참! 양쪽 모두 {left_val}이에요." if left_val == right_val else f"거짓. 왼쪽은 {left_val}, 오른쪽은 {right_val}이에요."
    except Exception:
        return "계산할 수 없어요."


def solve_problem(problem: str) -> str:
    problem = problem.strip()
    if not problem:
        return "문제를 입력해 주세요."
    if "=" in problem and not problem.startswith("="):
        return solve_equation(problem)
    try:
        expr = preprocess(problem)
        result = eval(expr, {"__builtins__": {}}, SAFE_FUNCTIONS)
        if isinstance(result, float) and result == int(result):
            result = int(result)
        return f"답: {result}"
    except ZeroDivisionError:
        return "오류: 0으로 나눌 수 없어요!"
    except Exception:
        return "풀 수 없는 문제예요. 수식을 다시 확인해 보세요."


# ── API 엔드포인트 ────────────────────────────────────────────────────────────

class SolveRequest(BaseModel):
    problem: str


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/api/solve")
def api_solve(req: SolveRequest):
    return {"result": solve_problem(req.problem)}


@app.post("/api/recognize")
async def api_recognize(image: UploadFile = File(...)):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "서버에 API 키가 설정되지 않았어요."}, 500

    media_type_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
    }
    ext = os.path.splitext(image.filename)[1].lower()
    media_type = media_type_map.get(ext, "image/jpeg")
    image_data = base64.standard_b64encode(await image.read()).decode("utf-8")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                {"type": "text", "text": "이 사진에서 수학 문제나 수식을 찾아서 텍스트로만 적어줘. 설명 없이 수식이나 방정식만 딱 한 줄로 출력해. 예: 3 + 5  또는  2x + 4 = 10  또는  sqrt(16)"},
            ],
        }],
    )
    extracted = next((b.text.strip() for b in message.content if b.type == "text"), "")
    if not extracted:
        return {"error": "사진에서 수식을 찾지 못했어요."}
    return {"extracted": extracted, "result": solve_problem(extracted)}
