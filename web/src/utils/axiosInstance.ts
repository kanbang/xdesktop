import axios from 'axios'
import { useAuthStore } from '@/store/auth'
import router from '@/router'

const instance = axios.create({
  baseURL: '/cloud_api',
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded'
  },
})

instance.interceptors.request.use(config => {
  const authStore = useAuthStore()
  const token = authStore.token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

instance.interceptors.response.use(
  response => response,
  error => {
    if (error.response.status === 401) {
      const authStore = useAuthStore()
      authStore.clearToken()
      router.push({ name: 'Login' })
    }
    return Promise.reject(error)
  }
)

export default instance

