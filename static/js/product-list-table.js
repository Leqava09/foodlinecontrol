(function() {
    function transformProductListToTable() {

        if (!window.PRODUCT_DATA) {

            return;
        }
        
        const resultList = document.querySelector('#result_list');
        if (!resultList) {

            return;
        }

        const data = window.PRODUCT_DATA;
        const categories = data.categories;
        const productsByCategory = data.products_by_category;


        if (categories.length === 0) {

            return;
        }

        // Create tabs container
        const tabContainer = document.createElement('div');
        tabContainer.id = 'category-tabs-container';
        tabContainer.style.cssText = 'margin-bottom: 0px; margin-top: -50px; background-color: #ffffff; padding-top: 20px; border-bottom: 3px solid #2c5aa0; overflow: hidden;';

        // Create tab buttons
        const tabButtonsDiv = document.createElement('div');
        tabButtonsDiv.style.cssText = 'display: flex; gap: 12px; background-color: #ffffff; padding: 0 0 0 24px; justify-content: flex-start; flex-wrap: wrap;';

        categories.forEach((category, idx) => {
            const tabBtn = document.createElement('button');
            tabBtn.textContent = category;
            tabBtn.setAttribute('data-category', category);
            tabBtn.className = 'category-tab';
            if (idx === 0) {
                tabBtn.classList.add('active');
            }
            
            tabBtn.style.cssText = `
                padding: 12px 60px;
                border: 1px solid #ccc;
                background-color: ${idx === 0 ? '#2c5aa0' : '#f0f0f0'};
                color: ${idx === 0 ? '#ffffff' : '#333'};
                font-weight: ${idx === 0 ? 'bold' : 'normal'};
                cursor: pointer;
                font-size: 13px;
                white-space: nowrap;
                border-radius: 4px 4px 0 0;
                border-bottom: ${idx === 0 ? 'none' : '1px solid #ccc'};
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s ease;
            `;

            tabBtn.addEventListener('click', function(e) {
                e.preventDefault();
                window.showCategory(category);
                
                document.querySelectorAll('.category-tab').forEach(btn => {
                    btn.classList.remove('active');
                    btn.style.backgroundColor = '#f0f0f0';
                    btn.style.color = '#333';
                    btn.style.fontWeight = 'normal';
                    btn.style.borderBottom = '1px solid #ccc';
                });
                
                this.classList.add('active');
                this.style.backgroundColor = '#2c5aa0';
                this.style.color = '#ffffff';
                this.style.fontWeight = 'bold';
                this.style.borderBottom = 'none';
            });

            tabButtonsDiv.appendChild(tabBtn);
        });

        tabContainer.appendChild(tabButtonsDiv);
        resultList.parentNode.insertBefore(tabContainer, resultList);

        // Create tables for each category
        const tablesContainer = document.createElement('div');
		tablesContainer.id = 'tables-container';
		tablesContainer.style.cssText = 'background-color: #ffffff; background-image: none; margin-top: -3px;';

        categories.forEach((category, idx) => {
            const tableDiv = document.createElement('div');
            tableDiv.setAttribute('data-category-table', category);
            tableDiv.style.cssText = `display: ${idx === 0 ? 'block' : 'none'}; background-color: #ffffff; background-image: none;`;

            const newTable = createCategoryTable(category, productsByCategory[category]);
            tableDiv.appendChild(newTable);
            tablesContainer.appendChild(tableDiv);
        });

        resultList.parentNode.replaceChild(tablesContainer, resultList);

        window.showCategory = function(category) {
            document.querySelectorAll('[data-category-table]').forEach(div => {
                div.style.display = div.getAttribute('data-category-table') === category ? 'block' : 'none';
            });
        };

    }

    function createCategoryTable(category, products) {
        const container = document.createElement('div');
        container.style.cssText = 'width: 100%; background-color: #ffffff; background-image: none;';
        
        products.forEach((product, productIdx) => {
            const productWrapper = document.createElement('div');
            productWrapper.style.cssText = 'margin-bottom: 30px; background-color: #ffffff; background-image: none;';
            
            // COMPONENTS TABLE
            const componentTable = document.createElement('table');
            componentTable.className = 'product-table';
            componentTable.style.cssText = 'width: 100%; border-collapse: collapse; background-color: #ffffff; font-size: 12px; border: 1px solid #333;';

            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');
            headerRow.className = 'product-header-row';
            headerRow.style.cssText = 'background-color: #4a8fa5; color: white; border-bottom: 2px solid #333;';
            
            const headers = ['Product Name', 'Size', 'Category', 'Sub Category', 'Stock Item', 'Usage per unit', 'Unit of Measure'];
            headers.forEach((header, idx) => {
                const th = document.createElement('th');
                th.textContent = header;
                th.className = 'product-header-cell';
                const borderRight = idx === headers.length - 1 ? '1px solid #333' : '1px solid #fff';
                th.style.cssText = `padding: 12px; text-align: center; font-weight: bold; border-right: ${borderRight}; font-size: 13px; white-space: nowrap;`;
                headerRow.appendChild(th);
            });
            
            thead.appendChild(headerRow);
            componentTable.appendChild(thead);

            const tbody = document.createElement('tbody');
            const components = product.components;
            const mpcCount = product.main_product_component_count || 0;
            let componentRowCount = components ? components.length : 0;
            let recipeItemCount = 0;
            let recipeHeaderCount = 0;
            if (product.recipes) {
                product.recipes.forEach(r => {
                    if (r.items) recipeItemCount += r.items.length;
                });
                recipeHeaderCount = product.recipes.length;
            }

            // NO COMPONENTS CASE
            if (!components || components.length === 0) {
                const tr = document.createElement('tr');
                tr.style.cssText = 'border-bottom: 1px solid #ddd;';
                
                const tdName = document.createElement('td');
                tdName.style.cssText = 'padding: 10px; font-weight: bold; border-right: 1px solid #ddd; text-align: center;';
                const link = document.createElement('a');
                link.href = product.edit_url;
                link.textContent = product.name;
                link.style.cssText = 'color: #0066cc; text-decoration: none;';
                tdName.appendChild(link);
                tr.appendChild(tdName);

                const tdSize = document.createElement('td');
                tdSize.style.cssText = 'padding: 10px; text-align: center; border-right: 1px solid #ddd; font-size: 12px;';
                tdSize.textContent = product.size || '-';
                tr.appendChild(tdSize);
                
                const emptyTd = document.createElement('td');
                emptyTd.colSpan = 5;
                emptyTd.style.cssText = 'padding: 10px; color: #999; text-align: center; border-right: 1px solid #333;';
                emptyTd.textContent = 'No components';
                tr.appendChild(emptyTd);

                tbody.appendChild(tr);
            } else {
                // COMPONENT ROWS
                components.forEach((comp, compIdx) => {
                    const tr = document.createElement('tr');
                    const bgColor = compIdx < mpcCount ? '#e8f4f8' : '#ffffff';
                    tr.style.cssText = `border-bottom: 1px solid #ddd; background-color: ${bgColor} !important;`;

                    if (compIdx === 0) {
						const totalRowSpan = componentRowCount + recipeItemCount + recipeHeaderCount;
						
						// Check if this is the last component (to know if we need bottom border)
						const isLastComponent = compIdx === components.length - 1;
						const hasRecipes = product.recipes && product.recipes.length > 0;
						
						// Product Name cell
						const productNameTd = document.createElement('td');
						productNameTd.style.cssText = `
							padding: 10px;
							font-weight: bold;
							border-right: 1px solid #ddd;
							text-align: center;
							background-color: #ffffff;
							vertical-align: middle;
							line-height: 1.5;
							border-bottom: 2px solid #333;
						`;
						productNameTd.rowSpan = totalRowSpan;

						const link = document.createElement('a');
						link.href = product.edit_url;
						link.textContent = product.name;
						link.style.cssText = 'color: #0066cc; text-decoration: none; font-size: 12px; display: block;';
						productNameTd.appendChild(link);
						tr.appendChild(productNameTd);

						// Size cell
						const sizeTd = document.createElement('td');
						sizeTd.style.cssText = `
							padding: 10px;
							text-align: center;
							border-right: 1px solid #ddd;
							font-size: 12px;
							background-color: #ffffff;
							vertical-align: middle;
							border-bottom: 2px solid #333;
						`;
						sizeTd.rowSpan = totalRowSpan;
						sizeTd.textContent = product.size || '-';
						tr.appendChild(sizeTd);
					}

                    const cells = [comp.category, comp.sub_category, comp.stock_item, comp.usage, comp.unit];
                    cells.forEach((cellText, cellIdx) => {
                        const td = document.createElement('td');
                        const borderRight = cellIdx === cells.length - 1 ? '1px solid #333' : '1px solid #ddd';
                        td.style.cssText = `padding: 10px; text-align: center; border-right: ${borderRight}; font-size: 12px;`;
                        td.textContent = cellText;
                        tr.appendChild(td);
                    });

                    tbody.appendChild(tr);
                });
            }

            // RECIPE HEADER - darker pink (ONE LINE spanning ALL columns)
			if (product.recipes && product.recipes.length > 0) {
				const recipeHeaderTr = document.createElement('tr');
				recipeHeaderTr.style.cssText = 'background-color: #f8bbd0; border-bottom: 1px solid #ec407a;';
				
				// Single cell spanning ALL 7 columns
				const recipeTd = document.createElement('td');
				recipeTd.colSpan = 7;  // CHANGED from 5 to 7 to span all columns
				recipeTd.style.cssText = 'padding: 10px; text-align: center; border: none; border-right: 1px solid #333; font-size: 12px; font-weight: bold;';
				
				const firstRecipe = product.recipes[0];
				const recipeText = `Recipes - ${firstRecipe.recipe_category} - ${firstRecipe.recipe_name} - ${firstRecipe.standard_usage_per_production_unit || '-'} ${firstRecipe.measure_unit || '-'}`;
				recipeTd.textContent = recipeText;
				
				recipeHeaderTr.appendChild(recipeTd);
				tbody.appendChild(recipeHeaderTr);
			}

            // RECIPE ROWS
            if (product.recipes && product.recipes.length > 0) {
                product.recipes.forEach((recipe, recipeIdx) => {
                    if (recipe.items && recipe.items.length > 0) {
                        recipe.items.forEach((item, itemIdx) => {
                            const isLastRecipeItem = recipeIdx === product.recipes.length - 1 && itemIdx === recipe.items.length - 1;
                            const tr = document.createElement('tr');
                            const borderBottom = isLastRecipeItem ? '2px solid #333' : '1px solid #f8bbd0';
                            tr.style.cssText = `border-bottom: ${borderBottom}; background-color: #fce4ec;`;
                            
                            const cells = [item.category, item.sub_category, item.stock_item, item.usage, item.unit];
                            cells.forEach((cellText, cellIdx) => {
                                const td = document.createElement('td');
                                const borderRight = cellIdx === cells.length - 1 ? '1px solid #333' : '1px solid #f8bbd0';
                                td.style.cssText = `padding: 10px; text-align: center; border-right: ${borderRight}; font-size: 12px; background-color: #fce4ec;`;
                                td.textContent = cellText;
                                tr.appendChild(td);
                            });
                            
                            tbody.appendChild(tr);
                        });
                    }
                });
            }

            componentTable.appendChild(tbody);
            productWrapper.appendChild(componentTable);
            container.appendChild(productWrapper);
        });
        
        return container;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', transformProductListToTable);
    } else {
        transformProductListToTable();
    }

    setTimeout(transformProductListToTable, 500);

})();
