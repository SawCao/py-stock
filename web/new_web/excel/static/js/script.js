async function fetchSheet(sheet) {
    const response = await fetch(`/static/spreadsheets/${sheet}`);
    const dataArrayBuffer = await response.arrayBuffer();
    return dataArrayBuffer;
  }

  function showLoadingIndicator() {
    document.getElementById("loading-indicator").style.display = "block";
  }

  function hideLoadingIndicator() {
      document.getElementById("loading-indicator").style.display = "none";
  }
  async function refreshSheets() {
    showLoadingIndicator(); // Show loading indicator
    const sheetOneArrayBuffer = await fetchSheet("one.xlsx");
    const sheetTwoArrayBuffer = await fetchSheet("two.xlsx");

    const sheetOneContent = readExcelFile(sheetOneArrayBuffer);
    const sheetTwoContent = readExcelFile(sheetTwoArrayBuffer);

    document.querySelector("#sheet-one").innerHTML = sheetOneContent;
    document.querySelector("#sheet-two").innerHTML = sheetTwoContent;

    hideLoadingIndicator(); // Hide loading indicator
}
  function readExcelFile(dataArrayBuffer) {
    const workbook = XLSX.read(dataArrayBuffer, { type: 'array' });
    const firstSheetName = workbook.SheetNames[0];
    const firstWorksheet = workbook.Sheets[firstSheetName];
  
    // Render an HTML table from the sheet data
    const htmlContent = XLSX.utils.sheet_to_html(firstWorksheet);
    return htmlContent;
  }
  
  document.addEventListener("DOMContentLoaded", async () => {
    const sheetOneArrayBuffer = await fetchSheet("one.xlsx");
    const sheetTwoArrayBuffer = await fetchSheet("two.xlsx");
  
    const sheetOneContent = readExcelFile(sheetOneArrayBuffer);
    const sheetTwoContent = readExcelFile(sheetTwoArrayBuffer);
  
    document.querySelector("#sheet-one").innerHTML = sheetOneContent;
    document.querySelector("#sheet-two").innerHTML = sheetTwoContent;
  
    const form = document.querySelector("#editor-form");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
  
      const formData = new FormData(form);
      const response = await fetch("/update-data", {
        method: "POST",
        body: formData,
      });
      const newData = await response.json();
  
      // UPDATE THE PAGE WITH NEW DATA HERE
          // Add this line to refresh the sheets after submitting the form
      await refreshSheets();
    });
    applyAutoResize();

  });


function autoResize(element) {
    element.style.height = 'auto';
    element.style.height = element.scrollHeight + 'px';
}

function applyAutoResize() {
    const autoResizeElements = document.querySelectorAll('.autoresize');
    autoResizeElements.forEach((element) => {
        autoResize(element);
        element.addEventListener('input', () => {
            autoResize(element);
        });
    });
}