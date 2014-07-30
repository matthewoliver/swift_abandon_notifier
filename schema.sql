SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='TRADITIONAL,ALLOW_INVALID_DATES';

DROP SCHEMA IF EXISTS `abandon` ;
CREATE SCHEMA IF NOT EXISTS `abandon` DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci ;
USE `abandon` ;

-- -----------------------------------------------------
-- Table `abandon`.`changes`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `abandon`.`changes` ;

CREATE TABLE IF NOT EXISTS `abandon`.`changes` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `number` INT NOT NULL,
  `mergeable` TINYINT(1) NULL,
  `branch` VARCHAR(255) NULL,
  `subject` TEXT NOT NULL,
  `created` DATETIME NOT NULL,
  `updated` DATETIME NOT NULL,
  `owner` VARCHAR(255) NOT NULL,
  `username` VARCHAR(255) NULL,
  `email` VARCHAR(255) NOT NULL,
  `deleted` TINYINT(1) NULL,
  `deleted_at` DATETIME NULL,
  PRIMARY KEY (`id`))
ENGINE = InnoDB;

-- -----------------------------------------------------
-- Table `abandon`.`notifications`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `abandon`.`notifications` ;

CREATE TABLE IF NOT EXISTS `abandon`.`notifications` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `type` VARCHAR(45) NULL DEFAULT 'email',
  `sent` TINYINT(1) NULL DEFAULT false,
  `email` VARCHAR(255) NULL,
  `date_sent` DATETIME NULL,
  `change_id` INT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_notifications_1`
    FOREIGN KEY (`change_id`)
    REFERENCES `abandon`.`changes` (`id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;

CREATE INDEX `fk_notifications_1_idx` ON `abandon`.`notifications` (`change_id` ASC);


-- -----------------------------------------------------
-- Table `abandon`.`options`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `abandon`.`options` ;

CREATE TABLE IF NOT EXISTS `abandon`.`options` (
  `key` VARCHAR(150) NOT NULL,
  `value` VARCHAR(150) NULL,
  PRIMARY KEY (`key`))
ENGINE = InnoDB;


SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;

