var dataset = document.currentScript.dataset;
for (var field in dataset) {
  window[field] = dataset[field];
}
