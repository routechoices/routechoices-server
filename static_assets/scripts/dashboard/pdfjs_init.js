const pdfjsPath = "/static/vendor/pdfjs-5.7.284/";

window.pdfjsLibReady = import(`${pdfjsPath}pdf.min.mjs`).then((pdfjsLib) => {
	pdfjsLib.GlobalWorkerOptions.workerSrc = `${pdfjsPath}pdf.worker.min.mjs`;
	return pdfjsLib;
});
