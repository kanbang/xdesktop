<template>
  <div class="login-container">
    <canvas ref="canvasRef"></canvas>
    <div class="glass-panel">
      <div class="login-card">
        <h1>欢迎回来</h1>
        <form @submit.prevent="handleLogin">
          <div class="input-group">
            <input type="text" v-model="username" placeholder="用户名" required />
          </div>
          <div class="input-group">
            <input type="password" v-model="password" placeholder="密码" required />
          </div>
          <button type="submit" class="login-button">登录</button>
        </form>
        <!-- <p class="footer-text">还没有账户？<a href="#">注册</a></p> -->
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, provide } from 'vue'
import { useRouter } from 'vue-router'

const username = ref('')
const password = ref('')
const router = useRouter()
const token = ref('')

const handleLogin = async () => {
  // 这里可以添加实际的登录逻辑，比如调用 API
  // 假设登录成功后，获取 token
  token.value = 'your-token-here'
  provide('authToken', token.value)
  router.push('/explorer')
}

// 动态特逻辑
const canvasRef = ref<HTMLCanvasElement | null>(null)
let animationId: number

const particles: Particle[] = []
const numParticles = 100
let mouseX = 0
let mouseY = 0

interface Particle {
  x: number
  y: number
  dx: number
  dy: number
  radius: number
  color: string
}

const initParticles = (width: number, height: number) => {
  for (let i = 0; i < numParticles; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      dx: (Math.random() - 0.5) * 0.5,
      dy: (Math.random() - 0.5) * 0.5,
      radius: Math.random() * 2 + 1,
      color: `rgba(0, 150, 136, 0.7)`, // 使用对比鲜明的绿色
    })
  }
}

const animate = (ctx: CanvasRenderingContext2D, width: number, height: number) => {
  ctx.clearRect(0, 0, width, height)
  particles.forEach((p) => {
    p.x += p.dx
    p.y += p.dy

    // 鼠标交互：粒子靠近鼠标时稍微加速
    const distanceX = p.x - mouseX
    const distanceY = p.y - mouseY
    const distance = Math.sqrt(distanceX * distanceX + distanceY * distanceY)
    if (distance < 100) {
      p.dx += distanceX * -0.0005
      p.dy += distanceY * -0.0005
    }

    // 边界反弹
    if (p.x + p.radius > width || p.x - p.radius < 0) p.dx *= -1
    if (p.y + p.radius > height || p.y - p.radius < 0) p.dy *= -1

    // 制粒子
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2)
    ctx.fillStyle = p.color
    ctx.fill()
  })

  animationId = requestAnimationFrame(() => animate(ctx, width, height))
}

const resizeCanvas = () => {
  const canvas = canvasRef.value
  if (canvas) {
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
    particles.length = 0
    initParticles(canvas.width, canvas.height)
  }
}

const handleMouseMove = (event: MouseEvent) => {
  mouseX = event.clientX
  mouseY = event.clientY
}

onMounted(() => {
  const canvas = canvasRef.value
  if (canvas) {
    const ctx = canvas.getContext('2d')
    if (ctx) {
      resizeCanvas()
      window.addEventListener('resize', resizeCanvas)
      window.addEventListener('mousemove', handleMouseMove)

      animate(ctx, canvas.width, canvas.height)
    }
  }
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animationId)
  window.removeEventListener('resize', resizeCanvas)
  window.removeEventListener('mousemove', handleMouseMove)
})
</script>


<style scoped>
.login-container {
  position: relative;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: linear-gradient(to bottom, #e0f7fa, #ffffff);
  /* 更柔和的背景渐变 */
}

#canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: -1;
}

.glass-panel {
  position: absolute;
  right: 0;
  top: 0;
  height: 100%;
  width: 600px;
  /* 固定宽度 */
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(3px);
  /* 毛玻璃效果 */
  box-shadow: -1px 0 10px rgba(128, 128, 128, 0.1);
  z-index: 1;
}

.login-card {
  width: 300px;
  /* 固定宽度 */
  background: rgba(255, 255, 255, 0.8);
  padding: 2rem;
  border-radius: 10px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  text-align: center;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

h1 {
  margin-bottom: 1.5rem;
  color: #00796b;
}

.input-group {
  margin-bottom: 1rem;
}

input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #b2dfdb;
  border-radius: 5px;
  font-size: 1rem;
  transition: border-color 0.3s;
}

input:focus {
  border-color: #00796b;
  outline: none;
}

.login-button {
  width: 100%;
  padding: 0.75rem;
  background-color: #00796b;
  color: white;
  border: none;
  border-radius: 5px;
  font-size: 1rem;
  cursor: pointer;
  transition: background-color 0.3s;
}

.login-button:hover {
  background-color: #004d40;
}

.footer-text {
  margin-top: 1rem;
  font-size: 0.9rem;
}

.footer-text a {
  color: #00796b;
  text-decoration: none;
}

.footer-text a:hover {
  text-decoration: underline;
}
</style>
