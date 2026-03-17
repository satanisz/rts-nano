"""Game-wide constants used for rendering, simulation, and balancing.

Attributes:
    SCREEN_WIDTH: Width of the game window in pixels.
    SCREEN_HEIGHT: Height of the game window in pixels.
    BOTTOM_MENU_HEIGHT: Height of the lower UI panel in pixels.
    WHITE: RGB tuple for white.
    BLACK: RGB tuple for black.
    RED: RGB tuple for red.
    GREEN: RGB tuple for green.
    BLUE: RGB tuple for blue.
    YELLOW: RGB tuple for yellow.
    CYAN: RGB tuple for cyan.
    GRAY: RGB tuple for gray.
    FPS: Target frames per second.
    RESOURCE_SIZE: Display size for resource entities.
    RESOURCE_RADIUS: Interaction radius for resource entities.
    HARVEST_SEARCH_RADIUS: Maximum radius for searching replacement resources.
    BUILDING_SIZE: Display size for buildings.
    BUILDING_RADIUS: Interaction radius for buildings.
    UNIT_SPEED: Base peasant movement speed.
    UNIT_SIZE: Display size for peasants.
    UNIT_RADIUS: Interaction radius for peasants.
    UNIT_MAX_CARRY: Maximum peasant carrying capacity.
    UNIT_LIFE: Base peasant life.
    UNIT_ATTACK_DAMAGE: Base peasant attack damage.
    UNIT_ATTACK_RANGE: Base peasant attack range.
    UNIT_ATTACK_SPEED: Base peasant attack speed.
    UNIT_ATTACK_IDLE: Base peasant idle ticks between attacks.
    UNIT_ATTACK_MODIFIER: Base peasant attack modifier.
    UNIT_SHIELD_MODIFIER: Base peasant shield modifier.
    UNIT_ATTACK_TYPE: Base peasant attack type.
    KNIGHT_SPEED: Knight movement speed.
    KNIGHT_SIZE: Knight display size.
    KNIGHT_RADIUS: Knight interaction radius.
    KNIGHT_MAX_CARRY: Knight carrying capacity.
    KNIGHT_LIFE: Knight life.
    KNIGHT_ATTACK_DAMAGE: Knight attack damage.
    KNIGHT_ATTACK_RANGE: Knight attack range.
    KNIGHT_ATTACK_SPEED: Knight attack speed.
    KNIGHT_ATTACK_IDLE: Knight idle ticks between attacks.
    KNIGHT_ATTACK_MODIFIER: Knight attack modifier.
    KNIGHT_SHIELD_MODIFIER: Knight shield modifier.
    KNIGHT_ATTACK_TYPE: Knight attack type.
    ARCHER_SPEED: Archer movement speed.
    ARCHER_SIZE: Archer display size.
    ARCHER_RADIUS: Archer interaction radius.
    ARCHER_MAX_CARRY: Archer carrying capacity.
    ARCHER_LIFE: Archer life.
    ARCHER_ATTACK_DAMAGE: Archer attack damage.
    ARCHER_ATTACK_RANGE: Archer attack range.
    ARCHER_ATTACK_SPEED: Archer attack speed.
    ARCHER_ATTACK_IDLE: Archer idle ticks between attacks.
    ARCHER_ATTACK_MODIFIER: Archer attack modifier.
    ARCHER_SHIELD_MODIFIER: Archer shield modifier.
    ARCHER_ATTACK_TYPE: Archer attack type.
    MAGE_SPEED: Mage movement speed.
    MAGE_SIZE: Mage display size.
    MAGE_RADIUS: Mage interaction radius.
    MAGE_MAX_CARRY: Mage carrying capacity.
    MAGE_LIFE: Mage life.
    MAGE_ATTACK_DAMAGE: Mage attack damage.
    MAGE_ATTACK_RANGE: Mage attack range.
    MAGE_ATTACK_SPEED: Mage attack speed.
    MAGE_ATTACK_IDLE: Mage idle ticks between attacks.
    MAGE_ATTACK_MODIFIER: Mage attack modifier.
    MAGE_SHIELD_MODIFIER: Mage shield modifier.
    MAGE_ATTACK_TYPE: Mage attack type.
"""


SCREEN_WIDTH = 1600
SCREEN_HEIGHT = 720
BOTTOM_MENU_HEIGHT = 120

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)
GRAY = (128, 128, 128)

FPS: int = 60
RESOURCE_SIZE: int = 15
RESOURCE_RADIUS: float = 5.0
HARVEST_SEARCH_RADIUS: float = 300.0

BUILDING_SIZE: int = 40
BUILDING_RADIUS: float = 10.0

UNIT_SPEED: float = 2.0
UNIT_SIZE: int = 30
UNIT_RADIUS: float = 10.0
UNIT_MAX_CARRY: int = 10
UNIT_LIFE: int = 5
UNIT_ATTACK_DAMAGE: int = 3
UNIT_ATTACK_RANGE: int = 0
UNIT_ATTACK_SPEED: int = 1
UNIT_ATTACK_IDLE: int = 10
UNIT_ATTACK_MODIFIER: int = 0
UNIT_SHIELD_MODIFIER: int = 0
UNIT_ATTACK_TYPE: str = "Melee"

KNIGHT_SPEED: float = 2.5
KNIGHT_SIZE: int = 40
KNIGHT_RADIUS: float = 13.0
KNIGHT_MAX_CARRY: int = 3
KNIGHT_LIFE: int = 100
KNIGHT_ATTACK_DAMAGE: int = 10
KNIGHT_ATTACK_RANGE: int = 50
KNIGHT_ATTACK_SPEED: int = 1
KNIGHT_ATTACK_IDLE: int = 10
KNIGHT_ATTACK_MODIFIER: int = 0
KNIGHT_SHIELD_MODIFIER: int = 0
KNIGHT_ATTACK_TYPE: str = "Melee"

ARCHER_SPEED: float = 2.0
ARCHER_SIZE: int = 40
ARCHER_RADIUS: float = 13.0
ARCHER_MAX_CARRY: int = 2
ARCHER_LIFE: int = 70
ARCHER_ATTACK_DAMAGE: int = 5
ARCHER_ATTACK_RANGE: int = 50
ARCHER_ATTACK_SPEED: int = 1
ARCHER_ATTACK_IDLE: int = 10
ARCHER_ATTACK_MODIFIER: int = 0
ARCHER_SHIELD_MODIFIER: int = 0
ARCHER_ATTACK_TYPE: str = "Ranged"

MAGE_SPEED: float = 1.5
MAGE_SIZE: int = 40
MAGE_RADIUS: float = 13.0
MAGE_MAX_CARRY: int = 1
MAGE_LIFE: int = 30
MAGE_ATTACK_DAMAGE: int = 5
MAGE_ATTACK_RANGE: int = 50
MAGE_ATTACK_SPEED: int = 1
MAGE_ATTACK_IDLE: int = 10
MAGE_ATTACK_MODIFIER: int = 0
MAGE_SHIELD_MODIFIER: int = 0
MAGE_ATTACK_TYPE: str = "Ranged"
