// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

interface InterfaceSimples {
    function set(uint256 _data) external;
    function get() external view returns (uint256);
}