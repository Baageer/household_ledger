Component({ properties: { item: Object }, methods: { onTap() { this.triggerEvent('select', { item: this.data.item }) } } })
