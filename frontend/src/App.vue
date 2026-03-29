<template>
  <router-view />
</template>

<style>
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  --color-primary: #1F4E79;
  --color-primary-light: #2E75B6;
  --color-primary-dark: #17375E;
  --color-success: #27AE60;
  --color-warning: #F39C12;
  --color-danger: #E74C3C;
  --color-bg: #F4F6F9;
  --color-surface: #FFFFFF;
  --color-border: #DDE1E7;
  --color-text: #1A1A2E;
  --color-text-secondary: #6B7280;
  --radius: 8px;
  --shadow: 0 1px 4px rgba(0,0,0,.10);
}

body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
  line-height: 1.5;
}

a { color: inherit; text-decoration: none; }

button {
  cursor: pointer;
  font-family: inherit;
}
</style>
