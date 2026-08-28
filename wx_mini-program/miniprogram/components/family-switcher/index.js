const app = getApp()
Component({ properties: { families: { type: Array, value: [] } }, methods: { choose(e) { const item = this.data.families[e.detail.value]; if (!item) return; app.setSession({ currentFamilyId: item.id }); this.triggerEvent('change', item) } } })
