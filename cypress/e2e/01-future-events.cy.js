context("Events in future", () => {
	it("Future events are not listed", () => {
		cy.visit("https://kimito-sk.rtchs.localhost/");
		cy.contains("My Future").should("not.exist");
	});

	it("Can not see Event as in future", () => {
		cy.visit("https://kimito-sk.rtchs.localhost/future-default/");
		cy.contains("Event has not yet started.");
		cy.contains("Starting in").should("be.visible");
	});

	it("Can not register or upload to Event as registration not open", () => {
		cy.visit(
			"https://dashboard.rtchs.localhost/contribute/kimito-sk/future-default/",
			{
				failOnStatusCode: false,
			},
		);
		cy.get("#registration-form").should("not.exist");
		cy.get("#upload-form").should("not.exist");
	});

	it("Can not export Event as it is not yet started", () => {
		cy.visit("https://kimito-sk.rtchs.localhost/future-default/export");
		cy.contains("Export is not available yet...");
	});

	it("Can register to an Event if open registration", () => {
		cy.visit(
			"https://dashboard.rtchs.localhost/contribute/kimito-sk/future-open-registration/",
		);
		cy.contains("Register");
		cy.get("#id_name").type("Thierry Gueorgiou");
		cy.get("#id_short_name").type("🇫🇷 T.Gueorgiou");
		cy.get("#id_device_id-ts-control").type("123456").wait(1000).blur();
		cy.get("button:not([type]),button[type=submit]").eq(0).click();
		cy.contains("Registration successful!");
	});

	it("Can not upload to an Event even if upload allowed since it is not yet started", () => {
		cy.visit(
			"https://dashboard.rtchs.localhost/contribute/kimito-sk/future-upload-allowed/",
			{ failOnStatusCode: false },
		);
		cy.get("#registration-form").should("not.exist");
		cy.get("#upload-form").should("not.exist");
	});

	it("Can only add competitor and not upload route to an Event even if everything allowed since it is not yet started", () => {
		cy.visit(
			"https://dashboard.rtchs.localhost/contribute/kimito-sk/future-open-registration-upload-allowed/",
		);
		cy.get("#registration-form").should("exist");
		cy.get("#upload-form").should("not.exist");
	});
});
