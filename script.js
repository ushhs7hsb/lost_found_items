$(document).ready(function() {
    // Handle answer submission
    $('.answer-form').submit(function(e) {
        e.preventDefault();
        const form = $(this);
        $.ajax({
            type: 'POST',
            url: form.attr('action'),
            data: form.serialize(),
            success: function(response) {
                if (response.contact) {
                    $('#contact-info').html(`Contact: ${response.contact}`).show();
                } else {
                    alert('Incorrect answers! Please try again.');
                }
            }
        });
    });
});