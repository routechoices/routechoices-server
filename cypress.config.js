const { defineConfig } = require("cypress");

module.exports = defineConfig({
  chromeWebSecurity: true,

  e2e: {
    // We've imported your old cypress plugins here.
    // You may want to clean this up later by importing these.
    setupNodeEvents(on, config) {
      return require("./cypress/plugins/index.js")(on, config);
    },
    baseUrl: "https://www.routechoices.dev",
  },
  hosts: {
    "*.routechoices.dev": "127.0.0.1",
  },
  component: {
    devServer: {
      framework: "create-react-app",
      bundler: "webpack",
    },
  },
});
