const makeFieldRandomizable = (id) => {
	u(id)
		.parent()
		.find(".form-text")
		.text("")
		.append(
			'<button class="randomize_btn btn btn-info btn-sm py-1 px-2" type="button"><i class="fa-solid fa-shuffle"></i> Randomize</button>',
		);
	u(".randomize_btn").on("click", function (e) {
		e.preventDefault();
		const target = u(this).closest(":has(.form-control)").find(".form-control");
		let result = "";
		const characters = "23456789abcdefghijkmnpqrstuvwxyz";
		const charactersLength = characters.length;
		for (let i = 0; i < 6; i++) {
			result += characters.charAt(Math.floor(Math.random() * charactersLength));
		}
		target.val(result);
		target.trigger("blur");
	});
};

const makeFieldNowable = (el) => {
	const localTimeDisplay = u(el)
		.parent()
		.addClass("text-nowrap text-end")
		.find(".local_time");
	localTimeDisplay.before(
		'<button class="set_time_now_btn btn btn-info btn-sm py-1 px-2" type="button"><i class="fa-solid fa-clock"></i> Set Now</button>',
	);
	u(el)
		.parent()
		.find(".set_time_now_btn")
		.on("click", function (e) {
			e.preventDefault();
			const target = u(this).closest(":has(input)").find("input");
			target.val(dayjs().local().format("YYYY-MM-DD HH:mm:ss"));
			target.trigger("change");
		});
};

const makeTimeFieldClearable = (el) => {
	const localTimeDisplay = u(el)
		.parent()
		.addClass("text-nowrap text-end")
		.find(".local_time");
	localTimeDisplay.before(
		'<button class="set_time_null_btn btn btn-info btn-sm py-1 px-2 ms-1" type="button"><i class="fa-solid fa-xmark"></i> Clear</button>',
	);
	u(el)
		.parent()
		.find(".set_time_null_btn")
		.on("click", function (e) {
			e.preventDefault();
			const target = u(this).closest(":has(input)").find("input");
			target.val("");
			target.trigger("change");
		});
};

const makeTextAreasAutoGrow = () => {
	u("textarea").wrap('<div class="grow-wrap"/>');
	u("textarea").each((el) => {
		el.addEventListener("input", (e) => {
			e.target.parentNode.dataset.replicatedValue = e.target.value;
		});
		u(el).trigger("input");
	});
};

(() => {
	u(".external-link").on("click", (e) => {
		const link = u(e.target).closest("a").attr("href");
		e.preventDefault();
		const confirmation = window.confirm(
			"You are about to exit the dashboard, continue?",
		);
		if (confirmation) {
			window.open(link);
		}
	});
})();
