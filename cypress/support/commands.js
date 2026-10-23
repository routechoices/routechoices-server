Cypress.Commands.add(
	"login",
	(username = "admin", password = "pa$$word123") => {
		cy.visit("https://dashboard.rtchs.localhost/login");
		cy.get("#id_login").type(username);
		cy.get("#id_password").type(`${password}{enter}`);
	},
);

Cypress.Commands.add("createClub", (name = "Kangasala SK") => {
	cy.visit("https://dashboard.rtchs.localhost/clubs/new");
	cy.get("#id_name").type(name);
	cy.get("button:not([type]),button[type=submit]").click();
	cy.contains("successfully");
});

Cypress.Commands.add(
	"createMap",
	(name = "Jukola 2019 - 1st Leg", club = "kimito-sk") => {
		cy.visit(`https://dashboard.rtchs.localhost/clubs/${club}/maps/new`);
		cy.fixture("Jukola2019/1/map.jpg", { encoding: null }).as("mapFile");
		cy.get("#id_image").selectFile({
			contents: "@mapFile",
			fileName:
				"Jukola2019 - 1 osuus_61.45075_24.18994_61.44656_24.24721_61.42094_24.23851_61.42533_24.18156_.jpg",
		});
		cy.get("#id_name").clear().type(name).blur();
		cy.get("#submit-btn").click();
		cy.location("pathname").should("eq", `/clubs/${club}/maps/`);
	},
);
