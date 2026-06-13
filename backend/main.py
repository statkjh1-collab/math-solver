import os
import base64
import json
import re
import math

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import sympy

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

# ── 기본 수학 계산 엔진 (간단한 수식용) ───────────────────────────────────────

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


def solve_basic(problem: str) -> str:
    problem = problem.strip()
    if not problem:
        return "문제를 입력해 주세요."
    try:
        expr = preprocess(problem)
        result = eval(expr, {"__builtins__": {}}, SAFE_FUNCTIONS)
        if isinstance(result, float) and result == int(result):
            result = int(result)
        return f"답: {result}"
    except ZeroDivisionError:
        return "오류: 0으로 나눌 수 없어요!"
    except Exception:
        return None  # sympy로 넘김


# ── sympy 풀이 엔진 ───────────────────────────────────────────────────────────

SYMPY_GLOBALS = {name: getattr(sympy, name) for name in dir(sympy) if not name.startswith('_')}
SYMPY_GLOBALS['__builtins__'] = {}

def run_sympy_code(code: str) -> str:
    """Claude가 생성한 sympy 코드를 안전하게 실행"""
    local_vars = {}
    try:
        exec(code, SYMPY_GLOBALS.copy(), local_vars)
        result = local_vars.get('result', None)
        steps = local_vars.get('steps', '')
        if result is None:
            return "결과를 계산하지 못했어요."
        answer = f"답: {result}"
        if steps:
            answer += f"\n\n풀이 과정:\n{steps}"
        return answer
    except Exception as e:
        return f"계산 오류: {e}"


# ── API 엔드포인트 ────────────────────────────────────────────────────────────

class SolveRequest(BaseModel):
    problem: str


class RecognizeRequest(BaseModel):
    image: str        # base64
    media_type: str = "image/jpeg"


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/api/solve")
def api_solve(req: SolveRequest):
    # 먼저 기본 엔진 시도, 안 되면 sympy 사용
    basic = solve_basic(req.problem)
    if basic:
        return {"result": basic}

    # sympy로 풀기
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"result": "풀 수 없는 문제예요."}

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"""다음 수학 문제를 sympy로 푸는 Python 코드를 작성해줘.
규칙:
- sympy 라이브러리만 사용 (import 없이 바로 사용 가능)
- 최종 답은 반드시 result 변수에 저장
- 풀이 과정은 steps 문자열 변수에 한국어로 저장
- 코드만 출력 (설명 없이)

문제: {req.problem}

예시 형식:
x = symbols('x')
solutions = solve(x**2 - 4, x)
result = solutions
steps = "x² = 4\\nx = ±2"
"""
        }]
    )
    code = message.content[0].text.strip()
    # 마크다운 코드블록 제거
    code = re.sub(r'```python\n?|```\n?', '', code).strip()
    return {"result": run_sympy_code(code)}


@app.post("/api/recognize")
async def api_recognize(req: RecognizeRequest):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="서버에 API 키가 설정되지 않았어요.")

    client = anthropic.Anthropic(api_key=api_key)

    # Step 1: Claude가 이미지에서 문제 파악 + sympy 코드 생성
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": req.media_type, "data": req.image}
                },
                {
                    "type": "text",
                    "text": """이 수학 문제 이미지를 분석해서 아래 JSON 형식으로만 답해줘 (다른 말 없이):

{
  "problem": "문제 전체 내용 (한국어로 요약)",
  "sympy_code": "sympy로 푸는 Python 코드. result 변수에 최종 답, steps 문자열에 풀이 과정 저장. import 없이 바로 sympy 함수 사용."
}

sympy_code 예시:
x = symbols('x')
eq = Rational(1,2)*x**2 - x + Rational(5,4)
roots = solve(eq, x)
alpha, beta = roots
result = simplify(alpha**16 + beta**16)
steps = "근의 공식으로 α, β를 구한 뒤 α¹⁶+β¹⁶ 계산"
"""
                }
            ]
        }]
    )

    raw = message.content[0].text.strip()

    # JSON 파싱
    try:
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            raise ValueError("JSON 없음")
        data = json.loads(json_match.group())
        problem_text = data.get("problem", "")
        sympy_code = data.get("sympy_code", "")
    except Exception:
        return {"extracted": raw, "result": "문제 파싱에 실패했어요."}

    # Step 2: sympy로 풀기
    solution = run_sympy_code(sympy_code)

    return {
        "extracted": problem_text,
        "result": solution,
        "sympy_code": sympy_code,
    }
