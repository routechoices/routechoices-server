const pdfjsPath = "vendor/pdfjs-5.7.284/";

window.pdfjsLibReady = import(`${window.local.staticRoot}${pdfjsPath}pdf.min.js`).then((pdfjsLib) => {
	pdfjsLib.GlobalWorkerOptions.workerSrc = `${window.local.staticRoot}${pdfjsPath}pdf.worker.min.js`;
	return pdfjsLib;
});
