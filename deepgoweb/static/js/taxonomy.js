$(function(){

    $( "#id_organism" ).autocomplete({
      source: function( request, response ) {
        $.ajax({
          url: "/deepgo/api/organisms",
          dataType: "json",
          data: {
            query: request.term
          },
          success: function( data ) {
            response($.map(data, function (item) {
		return {
                    name: item.name,
                    value: item.name,
		    id: item.id
		};
            }));
          }
        });
      },
      minLength: 3,
      select: function( event, ui ) {
          console.log( ui.item ?
		     "Selected: " + ui.item.id :
		       "Nothing selected, input was " + this.value);
	  if (ui.item) {
	      $('#id_org_id').val(ui.item.id);
	  }
      },
      open: function() {
        $( this ).removeClass( "ui-corner-all" ).addClass( "ui-corner-top" );
      },
      close: function() {
        $( this ).removeClass( "ui-corner-top" ).addClass( "ui-corner-all" );
      }
    });
});
