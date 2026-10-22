const pdfjsPath = "/static/vendor/pdfjs-6.4.299/";

window.pdfjsLibReady = import(`${pdfjsPath}pdf.js`).then((pdfjsLib) => {
	pdfjsLib.GlobalWorkerOptions.workerSrc = `${pdfjsPath}pdf.worker.js`;
	return pdfjsLib;
});
