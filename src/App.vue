<template>
  <div class="bg">
    <div class="card">
      <h1>수학 문제 풀이기 🧮</h1>
      <p class="subtitle">수식이나 방정식을 입력하고 [풀기] 버튼을 누르세요</p>

      <!-- 입력 -->
      <div class="input-row">
        <input v-model="problem" type="text" placeholder="예: 2x + 4 = 10" @keyup.enter="solve" />
        <button class="btn-solve" @click="solve">풀기</button>
      </div>

      <!-- 사진 버튼 -->
      <div class="photo-row">
        <a class="btn-photo" href="https://claude.ai" target="_blank" rel="noopener">
          📷 사진으로 문제 풀기
        </a>
        <span class="status-hint">Claude.ai에서 사진을 올려 풀 수 있어요</span>
      </div>

      <!-- 결과 -->
      <div class="result-box" :class="{ error: isError }">
        {{ result || '문제를 입력해 주세요.' }}
      </div>

      <!-- 예시 -->
      <div class="example-label">예시 문제</div>
      <div class="example-btns">
        <button v-for="ex in examples" :key="ex" class="btn-ex" @click="fillExample(ex)">{{ ex }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const problem = ref('')
const result = ref('')
const isError = ref(false)
const loading = ref(false)
const previewUrl = ref('')

const examples = ['125 ÷ 5 + 3', 'sqrt(144)', '2x + 4 = 10', '3x - 7 = 11', 'sin(30 * pi / 180)', '2^10']

async function solve() {
  if (!problem.value.trim()) { result.value = '문제를 입력해 주세요.'; return }
  isError.value = false
  try {
    const res = await fetch(`${API_URL}/api/solve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ problem: problem.value }),
    })
    const data = await res.json()
    result.value = data.result
  } catch {
    result.value = '서버에 연결할 수 없어요.'; isError.value = true
  }
}

async function uploadPhoto(e) {
  const file = e.target.files[0]
  if (!file) return
  previewUrl.value = URL.createObjectURL(file)
  loading.value = true; isError.value = false; result.value = ''

  const reader = new FileReader()
  reader.onload = async () => {
    const base64 = reader.result.split(',')[1]
    const mediaType = file.type || 'image/jpeg'
    try {
      const res = await fetch(`${API_URL}/api/recognize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: base64, media_type: mediaType }),
      })
      const data = await res.json()
      if (!res.ok) { result.value = data.detail || data.error || '오류가 발생했어요.'; isError.value = true }
      else {
        problem.value = data.extracted
        result.value = `[사진에서 읽은 문제]\n${data.extracted}\n\n${data.result}`
      }
    } catch (err) {
      result.value = '오류: ' + err.message; isError.value = true
    } finally {
      loading.value = false; e.target.value = ''
    }
  }
  reader.readAsDataURL(file)
}

function fillExample(ex) { problem.value = ex; solve() }
function clearPhoto() { previewUrl.value = ''; result.value = ''; problem.value = ''; isError.value = false }
</script>

<style scoped>
* { box-sizing: border-box; margin: 0; padding: 0; }

.bg {
  font-family: "맑은 고딕", "Malgun Gothic", sans-serif;
  background: linear-gradient(135deg, #e8eaf6 0%, #f3e5f5 100%);
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.card {
  background: white;
  border-radius: 20px;
  box-shadow: 0 8px 40px rgba(92, 107, 192, 0.15);
  width: 100%;
  max-width: 580px;
  padding: 36px 32px 28px;
}

h1 { text-align: center; font-size: 28px; color: #3a3a8c; margin-bottom: 6px; }
.subtitle { text-align: center; color: #888; font-size: 13px; margin-bottom: 20px; }

.input-row { display: flex; gap: 10px; margin-bottom: 12px; }
.input-row input {
  flex: 1; padding: 12px 16px; font-size: 16px; font-family: inherit;
  border: 2px solid #ccd; border-radius: 10px; outline: none; transition: border-color 0.2s;
}
.input-row input:focus { border-color: #5c6bc0; }
.btn-solve {
  padding: 12px 22px; background: #5c6bc0; color: white;
  border: none; border-radius: 10px; font-size: 15px; font-weight: bold;
  font-family: inherit; cursor: pointer; transition: background 0.2s;
}
.btn-solve:hover { background: #3f51b5; }

.photo-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.btn-photo {
  padding: 10px 18px; background: #43a047; color: white;
  border: none; border-radius: 10px; font-size: 14px; font-family: inherit;
  cursor: pointer; transition: background 0.2s;
}
.btn-photo:hover { background: #2e7d32; }
.status-hint { font-size: 12px; color: #888; }
.spinner {
  display: inline-block; width: 13px; height: 13px;
  border: 2px solid #ccc; border-top-color: #5c6bc0;
  border-radius: 50%; animation: spin 0.7s linear infinite;
  vertical-align: middle; margin-right: 4px;
}
@keyframes spin { to { transform: rotate(360deg); } }

.preview-wrap { position: relative; text-align: center; margin-bottom: 14px; }
.preview-wrap img { max-width: 100%; max-height: 200px; border-radius: 10px; border: 2px solid #e8eaf6; }
.btn-clear {
  position: absolute; top: 6px; right: 6px;
  background: rgba(0,0,0,0.5); color: white; border: none;
  border-radius: 50%; width: 26px; height: 26px; font-size: 14px;
  cursor: pointer; line-height: 26px; text-align: center;
}

.result-box {
  background: #f8f9ff; border: 1.5px solid #dde; border-radius: 12px;
  padding: 16px 18px; min-height: 110px; font-size: 15px; line-height: 1.9;
  color: #222; white-space: pre-wrap; word-break: break-word; margin-bottom: 22px;
}
.result-box.error { color: #c62828; background: #fff3f3; border-color: #ffcdd2; }

.example-label { font-size: 12px; font-weight: bold; color: #888; margin-bottom: 8px; }
.example-btns { display: flex; flex-wrap: wrap; gap: 8px; }
.btn-ex {
  padding: 6px 12px; background: #e8eaf6; color: #3a3a8c;
  border: none; border-radius: 8px; font-size: 13px; font-family: inherit;
  cursor: pointer; transition: background 0.15s;
}
.btn-ex:hover { background: #c5cae9; }
</style>
