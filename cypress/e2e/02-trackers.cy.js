context("GPS Tracker ID generation", () => {
	after(() => {
		cy.wait(100);
	});

	it("Genereate an GPS Tracker ID", () => {
		cy.visit("https:////www.rtchs.localhost/trackers");
		cy.get("#dedicated-trackers-tab").click();

		// Invalid too short IMEI
		cy.get("#IMEI").clear().type("0123456789");
		cy.get("button:not([type]),button[type=submit]").click();
		cy.contains("Invalid IMEI (must be 15 digits long)");
		cy.get("#copyDevIdBtn").should("not.be.visible");

		// Invalid (too long IMEI) but input takes only 15 chars
		cy.get("#IMEI").clear().type("0123456789012345");
		cy.get("button:not([type]),button[type=submit]").click();
		cy.contains("Invalid IMEI (check digit does not match)");
		cy.get("#copyDevIdBtn").should("not.be.visible");

		// Invalid: Luhn check
		cy.get("#IMEI").clear().type("012345678901234");
		cy.get("button:not([type]),button[type=submit]").click();
		cy.contains("Invalid IMEI (check digit does not match)");
		cy.get("#copyDevIdBtn").should("not.be.visible");

		// Valid
		cy.get("#IMEI").clear().type("012345678901237");
		cy.get("button:not([type]),button[type=submit]").click();
		cy.get("#copyDevIdBtn").should("be.visible");

		// Invalid: Contains a letter.          V This is letter "O"
		cy.get("#IMEI").clear().type("0123456789O1234");
		cy.get("button:not([type]),button[type=submit]").click();
		cy.contains("Invalid IMEI (should not contain letters)");
		cy.get("#copyDevIdBtn").should("not.be.visible");
	});
});
