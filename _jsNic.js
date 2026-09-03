$(window).on('scroll', function () {
    if ($(window).scrollTop()) {
        $('nav').addClass('special');


    }

    else {
        $('nav').removeClass('special');

    }
});

//logo change without USNIC when screen width less than 768px
$(function() {
    var resizeWindow = function() {
        var resizeWidth = screen.width;
        var x = document.getElementById("headerLogo");
        if (resizeWidth < 768) {
            x.src = "/images/home/USNIC_logo_noname.png";
        } else {
            x.src = "/images/home/USNIC_logo_smcolorwhite.png";
        }
    };
    resizeWindow();
    $(window).resize(resizeWindow);
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

function catalogHandler(region, period, posit) {

    $('.show').removeClass('show');
    $('div.acc-info').attr('aria-expanded', 'false');
    $('#' + region + 'Collapse').addClass('show');
    $('#' + region + 'Collapse').removeClass('collapsed');
    $('.' + region + '-call').attr('aria-expanded', 'true');
    $('a[data-target="#' + region + period + '"').attr('aria-expanded', 'true');
    $('#' + region + period).addClass('show');
    //$('a[data-target="#arcticDaily"]').closest('.card-header').addClass('nuts');
    //$('a.[aria-enabled="true"]').closest('div.card-header').css('background-color', 'yellow');

    $('a.' + region.substring(0, 3) + '-' + period.substring(0, 1).toLowerCase() + '-' + posit).contents().unwrap();
}

function linkChanger(product) {
    var region = product.substr(0, 3);
    $('.show').removeClass('show');
    $('#collapse-' + region).addClass('show');
    $('a[href="#collapse-' + region + '"]').removeClass('collapsed');
    $('a.card-link').attr('aria-expanded', 'false');
    $('a[href="#collapse-' + region + '"]').attr('aria-expanded', 'true');
    $('a.acc-' + product).contents().unwrap();
    $('.product-btn').removeClass('product-btn').addClass('product-no-btn');
    $('.btn-main-' + region).removeClass('product-no-btn').addClass('product-btn');
    $('.btn-' + product).removeClass('product-no-btn').addClass('product-btn');
    //$('[class*="-productbar"]').css("display", "none");
    //$('[class$="-productbar"]').hide();
    $('.' + region + '-productbar').removeClass('prod-btn-hide');
    $('.' + region + '-productbar').addClass('prod-btn-display');
}

//$('#card-body li').on('click',
//    function () {
//        $('li.monkey').removeClass('monkey');
//        $(this).addClass('monkey');
//    });