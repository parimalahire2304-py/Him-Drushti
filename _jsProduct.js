$(window).on('scroll', function () {
    if ($(window).scrollTop()) {
        $('nav').addClass('special');
    }

    else {
        $('nav').removeClass('special');
    }
});

$(function () {

    $(document).on('scroll', function () {

        if ($(window).scrollTop() > 200) {
            $('.scroll-top-wrapper').addClass('show');
        } else {
            $('.scroll-top-wrapper').removeClass('show');
        }
    });

    $('.scroll-top-wrapper').on('click', scrollToTop);
});

function scrollToTop() {
    document.body.scrollTop = 0;
    document.documentElement.scrollTop = 0;
};

{
    var prodAcc = document.getElementsByClassName("prod-acc");

    for (var i = 0; i < prodAcc.length; i++) {
        prodAcc[i].addEventListener('click', function () {
            this.classList.toggle('prod-acc-active');
            var otherSib = this.nextElementSibling;
            if (otherSib.style.maxHeight) {
                otherSib.style.maxHeight = null;
            } else {
                otherSib.style.maxHeight = otherSib.scrollHeight + 'px';
            }
        });
    }
}

//open product accordion menu based on region product is located in
$(document).ready(function () {

    //get current URL and split into array
    var urlSplit = document.URL.split('/');

    //get only the last element of urlSplit array
    var getPage = urlSplit.pop();

    if (getPage === "gl-forecast.htm") {
        $("#inglFcst").load("../hold/glFcst.htm");
        $("#inglOutlook").load("../hold/glOutlook.htm");
        $("#inglSummary").load("../hold/glSummary.htm");
    }

    //split getPage to get region area, which is deliminated with a '-'
    var getRegion = getPage.split('-');

    //assign region based on the first getRegion variable
    var prodRegion = (getRegion[0] === 'arc') ? '#prod-arctic' : (getRegion[0] === 'ant') ? '#prod-antarc' :
        (getRegion[0] === 'gl') ? '#prod-greatlakes' : '#prod-midatlantic';

    //simulate click to expand region of URL for prod-acc menu
    $(prodRegion).click();
});

function getHTML(fName) {

    $("#in" + fName).load("../hold/" + fName + ".htm");

}

//$("#outlook").click(function () {
//    var showing = document.getElementsByClassName('outlook-show');
//    if (showing.length > 0) {
//        document.getElementById('outlook').innerText = 'Hide';
//    } else {
//        document.getElementById('outlook').innerText = 'View';
//    }
//    $("#outlook-container").toggleClass("outlook-show");
//});

//function to load and display image into a modal
function openModal(title, imgName, refText) {

    $("#chartShow").empty(); //clear any data created from previous modal calls

    var refID = refText.getAttribute("href"); //retrieves href value of the element

    refID = refID.substring(1); //removes leading # character of href value

    var dtitle = title.replace(/ /g, "_");
    //html code placed in a variable to be passed into preset <div>
    var modalCode =
        '<div class="modal fade" id="' + refID + '" tabindex="-1" role="dialog" aria-labelledby="' + refID + 'Label" aria-hidden="true">' +
        '<div class="modal-dialog modal-dialog-centered modal-lg modal-xl" role="document">' +
        '<div class="modal-content">' +
        '<div class="modal-header">' +
        '<h5 class="modal-title" id="' + refID + 'Label">' + title + '</h5>' +
        '<button type="button" class="close" data-dismiss="modal" aria-label="Close">' +
        '<span aria-hidden="true">&times;</span>' +
        '</button>' +
        '</div>' +
        '<div class="modal-body">' +
        //'<img src="../pub/' + imgName + '" class="img-fluid rounded" />' +
        '<img src="' + imgName + '" class="img-fluid rounded" />' +
        '</div>' +
        '<div class="modal-footer">' +
        //'<button type="button" class="btn btn-secondary" onclick="window.open(\'../images/' + imgName + '\')">New Window</button>' +
        '<button type="button" class="btn btn-secondary" onclick="window.open(\'' + imgName + '\')">Enlarge</button>' +
        '<button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>' +
        //'<a href="../images/' + imgName + '" download><button type="button" class="btn btn-info">Download</button></a>' +
        //'<a href="' + imgName + '" download><button type="button" class="btn btn-info">Download</button></a>' +
        '<a href="' + imgName + '" id=' + dtitle +' class=' + refID + '_' + dtitle +'><button type="button" class="btn btn-info">Download</button></a>' +
        '</div>' +
        '</div>' +
        '</div>' +
        '</div>';

    $("#chartShow").append(modalCode); //passing html code to preset <div>
}

//function to load and display HTM file into modal
function openHTMLModal(title, refText) {

    var refID = refText.getAttribute("href"); //retrieves href value of the element

    refID = refID.substring(1); //removes leading # character of href value

    //html code placed in a variable to be passed into preset <div>
    var modalCode =
        '<div class="modal fade" id="' + refID + '" tabindex="-1" role="dialog" aria-labelledby="' + refID + 'Label" aria-hidden="true">' +
        '<div class="modal-dialog modal-dialog-centered modal-lg modal-xl" role="document">' +
        '<div class="modal-content">' +
        '<div class="modal-header">' +
        '<h5 class="modal-title" id="' + refID + 'Label">' + title + '</h5>' +
        '<button type="button" class="close" data-dismiss="modal" aria-label="Close">' +
        '<span aria-hidden="true">&times;</span>' +
        '</button>' +
        '</div>' +
        '<div class="modal-body">' +
        '<div id="in' + refID + '"></div>' +
        '<script>if (document.getElementById("in' + refID + '")) {' +
        '$("#in' + refID + '").load("../hold/' + refID + '.htm");}</script > ' +
        '</div>' +
        '<div class="modal-footer">' +
        '<button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>' +
        '</div>' +
        '</div>' +
        '</div>' +
        '</div>';

    $("#chartShow").append(modalCode); //passing html code to preset <div>
}

function pickerSet(minDate, maxDate) {
    var currentDate = new Date();
    var previousWeek = new Date();
    var preWeek = new Date(maxDate);
    preWeek.setDate(preWeek.getDate() - 7);
    previousWeek.setDate(previousWeek.getDate() - 7);
    var minYear = minDate.substring(6, 10);
    var maxYear = maxDate.substring(6, 10);
    //$('#enddate-pick').datepicker().datepicker("setDate", currentDate);
    //$('#startdate-pick').datepicker().datepicker("setDate", previousWeek);

    $("#startdate-pick").datepicker({
        //changeYear: true,
        dateFormat: 'mm/dd/yy',
        //defaultDate: new Date(pWeek), 
        showButtonPanel: true,
        changeMonth: true,
        changeYear: true,
        //showOn: "button",
        //buttonImage: "images/calendar.gif",
        //buttonImageOnly: true,
        yearRange: minYear + ':' + maxYear,
        minDate: new Date(minDate),
        maxDate: new Date(maxDate)
    //inline: true
    //});
}).datepicker("setDate", preWeek);

    $("#enddate-pick").datepicker({
        //changeYear: true,
        //dateFormat: 'mm/dd/yy',
        //defaultDate: cDate,
        showButtonPanel: true,
        changeMonth: true,
        changeYear: true,
        //showOn: "button",
        //buttonImage: "images/calendar.gif",
        //buttonImageOnly: true,
        yearRange: minYear + ':' + maxYear,
        minDate: new Date(minDate),
        maxDate: new Date(maxDate)
        //inline: true
    //});
    }).datepicker("setDate", maxDate);
}

function pickerUpdate(minDate, maxDate) {
    var currentDate = new Date();
    var previousWeek = new Date();
    previousWeek.setDate(previousWeek.getDate() - 7);
    var minYear = minDate.substring(6, 10);
    var maxYear = maxDate.substring(6, 10);

    $('#startdate-pick').datepicker('option', 'yearRange', minYear + ':' + maxYear);
    $('#startdate-pick').datepicker('option', 'minDate', minDate);
    $('#startdate-pick').datepicker('option', 'maxDate', maxDate);

    $('#enddate-pick').datepicker('option', 'yearRange', minYear + ':20120');
    $('#enddate-pick').datepicker('option', 'minDate', minDate);
    $('#enddate-pick').datepicker('option', 'maxDate', maxDate);
}

document.addEventListener(
    "DOMContentLoaded",
    () => {
        new Mmenu("#nic-menu",
            {
                extensions: ["pagedim-black", "popup"],
                navbar: { title: "Product Menu" },
                "autoHeight": true
            });
    });


