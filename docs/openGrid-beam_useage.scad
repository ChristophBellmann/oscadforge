include <BOSL2/std.scad>;
use <QuackWorks/openGrid/openGrid.scad>;
/*[Board Size]*/
Full_or_Lite = "Lite"; //[Full, Lite, Heavy]
Board_Width = 6;
Board_Height = 4;

    
//GENERATE SINGLE TILES
//openGrid(Board_Width=Board_Width, Board_Height=Board_Height, tileSize=Tile_Size, Tile_Thickness=Tile_Thickness, Screw_Mounting=Screw_Mounting, Chamfers=Chamfers, Add_Adhesive_Base=Add_Adhesive_Base, anchor=BOT, Connector_Holes=Connector_Holes);

openGridLite(Board_Width=Board_Width, Board_Height=Board_Height, Screw_Mounting="Corners", Chamfers="Corners", Add_Adhesive_Base=false, anchor=BOT, Connector_Holes=true);

