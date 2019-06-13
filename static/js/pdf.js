const img = document.querySelector('#marker');

function generatePdf() {
    const doc = new jsPDF();
    doc.addImage(img, 'PNG', 0, 0, 200, 200);
    doc.save();
}