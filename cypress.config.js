const { defineConfig } = require("cypress");

import { execSync } from "child_process";

module.exports = defineConfig({
	chromeWebSecurity: true,
	e2e: {
		// We've imported your old cypress plugins here.
		// You may want to clean this up later by importing these.
		setupNodeEvents(on, config) {
			on("before:run", (details) => {
				execSync(
					"docker exec rc_django python /app/manage.py reset_db_for_e2e_tests",
				);
			});
			return require("./cypress/plugins/index.js")(on, config);
		},
		baseUrl: "https://dashboard.rtchs.localhost",
	},
	component: {
		devServer: {
			framework: "create-react-app",
			bundler: "webpack",
		},
	},
	pageLoadTimeout: 10000,
	video: true,
	screenshotOnRunFailure: true,
	allowCypressEnv: false,
});
