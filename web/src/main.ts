import './assets/main.css'
import 'virtual:uno.css'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import 'vuefinder/dist/style.css'

import VueFinder from 'vuefinder/dist/vuefinder'
import en from 'vuefinder/dist/locales/en.js'
import zhCN from 'vuefinder/dist/locales/zhCN.js'

const app = createApp(App)
app.use(VueFinder, {
    i18n: { en, zhCN },
    locale: 'zhCN',
})
app.use(router)

app.mount('#app')
