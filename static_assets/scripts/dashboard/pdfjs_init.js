const pdfjsPath = "/static/vendor/pdfjs-5.7.284/";

window.pdfjsLibReady = import(`${pdfjsPath}pdf.min.js`).then((pdfjsLib) => {
	pdfjsLib.GlobalWorkerOptions.workerSrc = `${pdfjsPath}pdf.worker.min.js`;
	return pdfjsLib;
});
