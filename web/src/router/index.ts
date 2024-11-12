import { createRouter, createWebHistory } from 'vue-router'
import Login from '@/views/login.vue'
import Explorer from '@/views/Explorer.vue'
import { useAuthStore } from '@/store/auth'
import { getActivePinia } from 'pinia'

const routes = [
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/explorer',
    name: 'Explorer',
    component: Explorer,
    meta: { requiresAuth: true }
  },
  {
    path: '/login',
    name: 'Login',
    component: Login
  }
]

const router = createRouter({
  history: createWebHistory('/'),
  routes
})

router.beforeEach((to, from, next) => {
  if (!getActivePinia()) {
    console.error('Pinia is not initialized')
    next(false) // 阻止导航
    return
  }

  const authStore = useAuthStore()
  if (to.matched.some(record => record.meta.requiresAuth)) {
    if (!authStore.isAuthenticated) {
      next({ name: 'Login' })
    } else {
      next()
    }
  } else {
    next()
  }
})

export default router 