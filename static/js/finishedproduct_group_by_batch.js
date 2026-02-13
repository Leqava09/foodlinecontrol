(function() {
  var $ = (window.django && django.jQuery) ? django.jQuery : window.jQuery;

  // indices in the combined td+th list
  var PROD_DATE_COL = 1;
  var BATCH_COL     = 2;
  var ACTIVITY_COL  = 6;

  var COLS_TO_MERGE = [0, 1, 2, 3, 4];

  function groupByBatch() {
    var $rows = $('#result_list tbody tr');

    if (!$rows.length) return;

    // Sort rows: Book In first, then by transaction date
    var sortedRows = $rows.sort(function(a, b) {
      var $cellsA = $(a).children('td,th');
      var $cellsB = $(b).children('td,th');
      
      var batchA = $.trim($cellsA.eq(BATCH_COL).text());
      var batchB = $.trim($cellsB.eq(BATCH_COL).text());
      
      // First, sort by batch
      if (batchA !== batchB) {
        return batchA.localeCompare(batchB);
      }
      
      // Same batch: check if Book In
      var activityA = $.trim($cellsA.eq(ACTIVITY_COL).text());
      var activityB = $.trim($cellsB.eq(ACTIVITY_COL).text());
      
      var isInA = activityA.indexOf('Book In') !== -1;
      var isInB = activityB.indexOf('Book In') !== -1;
      
      // Book In always comes first
      if (isInA && !isInB) return -1;
      if (!isInA && isInB) return 1;
      
      // Both are Book Out transactions: sort by transaction date
      if (!isInA && !isInB) {
        // Get transaction date (last column)
        var dateA = $.trim($cellsA.last().text());
        var dateB = $.trim($cellsB.last().text());
        
        // Convert to Date objects for comparison
        var dateObjA = new Date(dateA);
        var dateObjB = new Date(dateB);
        
        if (!isNaN(dateObjA) && !isNaN(dateObjB)) {
          return dateObjA - dateObjB; // Sort chronologically
        }
      }
      
      // Fallback: keep original order
      return 0;
    });
    
    $('#result_list tbody').append(sortedRows);

    var lastKey = null, $firstRow = null, blockCount = 0;
    var batchGroups = {};
    var groupIndex = 0;

	sortedRows.each(function() {
	  var $row   = $(this);
	  var $cells = $row.children('td,th');

	  var key  = $.trim($cells.eq(BATCH_COL).text());
	  var activity = $.trim($cells.eq(ACTIVITY_COL).text());
	  var isIn = activity.indexOf('Book In') !== -1;

	  // Track batch groups (do NOT apply colors here yet)
	  if (!batchGroups[key]) {
		batchGroups[key] = groupIndex;
		groupIndex++;
	  }

	  // Add transaction type classes
	  if (isIn) {
		$row.addClass('tx-in-row');
	  } else if (activity.indexOf('Dispatch') !== -1) {
		$row.addClass('tx-dispatch-row');
	  } else if (activity.indexOf('Transfer') !== -1) {
		$row.addClass('tx-transfer-row');
	  } else if (activity.indexOf('Damage') !== -1 || activity.indexOf('Scrap') !== -1) {
		$row.addClass('tx-scrap-row');
	  } else {
		$row.addClass('tx-out-row');
	  }

	  // Handle row merging
	  if (lastKey === null || key !== lastKey) {
		if ($firstRow && blockCount > 1) {
		  COLS_TO_MERGE.forEach(function(i) {
			$firstRow.children('td,th').eq(i).attr('rowspan', blockCount);
		  });
		}
		lastKey   = key;
		$firstRow = $row;
		blockCount = 1;
	  } else {
		blockCount += 1;
		COLS_TO_MERGE.forEach(function(i) {
		  $cells.eq(i).hide();
		});
	  }
	});

	if ($firstRow && blockCount > 1) {
	  COLS_TO_MERGE.forEach(function(i) {
		$firstRow.children('td,th').eq(i).attr('rowspan', blockCount);
	  });
	}

	// NOW apply colors to all rows based on their batch group
	sortedRows.each(function() {
	  var $row = $(this);
	  var $cells = $row.children('td,th');
	  var key = $.trim($cells.eq(BATCH_COL).text());
	  
	  // Apply color based on batch group index
	  if (batchGroups[key] % 2 === 0) {
		$row.attr('style', 'background-color: #e3f2fd !important');
	  } else {
		$row.attr('style', 'background-color: #e8f5e9 !important');
	  }
	});


    if ($firstRow && blockCount > 1) {
      COLS_TO_MERGE.forEach(function(i) {
        $firstRow.children('td,th').eq(i).attr('rowspan', blockCount);
      });
    }
  }

  $(window).on('load', groupByBatch);
})();
