import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/login.vue'
import ExplorerView from '../views/explorer.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/explorer',
      name: 'explorer',
      component: ExplorerView,
    },
  ],
})

export default router
