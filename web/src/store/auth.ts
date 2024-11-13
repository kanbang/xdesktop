import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('authToken') || '',
    username: localStorage.getItem('username') || '',
  }),
  getters: {
    isAuthenticated: (state) => !!state.token,
  },
  actions: {
    setToken(token: string) {
      this.token = token
      localStorage.setItem('authToken', token)
    },
    setUsername(username: string) {
      this.username = username
      localStorage.setItem('username', username)
    },
    clearToken() {
      this.token = ''
      localStorage.removeItem('authToken')
      localStorage.removeItem('username')
    }
  }
}) 